"""Copy a local PDF collection, then import small resumable batches via LabUI.

Originals are read only. Exact duplicates are detected by SHA-256, including
copies already in LabUI. An atomic manifest records every outcome. The staging
copy allows indexing to continue after removable storage is disconnected.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import sqlite3
import time

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def save_json(path: Path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix('.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding='utf-8')
    temporary.replace(path)


def fingerprint(path: Path):
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(4 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def slug(stem):
    return re.sub(r'_+', '_', re.sub(r'[^\w\-]', '_', stem)).strip('_')[:120]


def counts(manifest):
    return dict(Counter(item['status'] for item in manifest['files']))


def progress(data: Path, manifest, phase, message, **extra):
    save_json(data / 'rag/import_status.json', {
        'running': phase not in {'complete', 'error', 'prepared'}, 'phase': phase,
        'message': message, 'total': manifest['total'], 'processed': len(manifest['files']),
        'counts': counts(manifest), 'updated_at': datetime.now(timezone.utc).isoformat(), **extra,
    })
    print(message, flush=True)


def prepare(source: Path, data: Path, job: Path, manifest):
    import pymupdf
    if manifest.get('prepared'):
        return
    if not source.is_dir():
        raise RuntimeError(f'Source folder is unavailable: {source}')
    pdfs = sorted((p for p in source.rglob('*') if p.is_file() and p.suffix.lower() == '.pdf'
                   and not p.name.startswith('._')), key=lambda p: str(p.relative_to(source)).casefold())
    manifest['total'] = len(pdfs)
    seen = {item['sha256']: item.get('paper_id') or item['source'] for item in manifest['files'] if item.get('sha256')}
    for path in (data / 'papers').glob('*'):
        if path.is_file() and path.suffix.lower() == '.pdf':
            seen.setdefault(fingerprint(path), slug(path.stem))
    done = {item['source'] for item in manifest['files']}
    staging = job / 'pdfs'
    staging.mkdir(parents=True, exist_ok=True)
    for pdf in pdfs:
        relative = str(pdf.relative_to(source))
        if relative in done:
            continue
        item = {'source': relative, 'bytes': pdf.stat().st_size}
        temporary = staging / 'copy.part'
        digest = hashlib.sha256()
        with pdf.open('rb') as original, temporary.open('wb') as target:
            for chunk in iter(lambda: original.read(4 * 1024 * 1024), b''):
                digest.update(chunk)
                target.write(chunk)
        item['sha256'] = digest.hexdigest()
        if item['sha256'] in seen:
            item.update(status='duplicate', duplicate_of=seen[item['sha256']])
            temporary.unlink()
        else:
            try:
                with pymupdf.open(temporary, filetype='pdf') as document:
                    if document.needs_pass or not len(document):
                        raise ValueError('Encrypted or empty PDF')
                    item['pages'] = len(document)
                name = (slug(pdf.stem)[:90].rstrip('_') or 'paper') + '_' + item['sha256'][:12]
                item.update(status='staged', paper_id=name, filename=name + '.pdf')
                temporary.replace(staging / item['filename'])
                seen[item['sha256']] = name
            except Exception as exc:
                item.update(status='invalid', error=str(exc))
                temporary.unlink(missing_ok=True)
        manifest['files'].append(item)
        save_json(job / 'manifest.json', manifest)
        if len(manifest['files']) % 10 == 0:
            progress(data, manifest, 'copying', f"Copied and checked {len(manifest['files'])}/{len(pdfs)} PDFs")
    manifest['prepared'] = True
    save_json(job / 'manifest.json', manifest)
    progress(data, manifest, 'prepared', f"PDF copy complete: {counts(manifest)}")


def paper_ids(data):
    with sqlite3.connect(data / 'rag/rag.db', timeout=30) as conn:
        return {row[0] for row in conn.execute('SELECT paper_id FROM papers')}


def text_hash(parsed):
    text = ' '.join(section.get('text', '') for section in parsed.get('sections', []))
    return hashlib.md5(re.sub(r'[^a-z0-9]+', ' ', text.lower()).strip().encode()).hexdigest()


def find_content_duplicate(data, item, indexed):
    directory = data / 'rag/parsed'
    target = directory / (item['paper_id'] + '.json')
    if not target.exists():
        return None
    target_hash = text_hash(json.loads(target.read_text()))
    for name in indexed:
        candidate = directory / (name + '.json')
        if candidate.exists() and text_hash(json.loads(candidate.read_text())) == target_hash:
            return name
    return None


def reconcile_manifest(data, job, manifest):
    """Repair old importer IDs using the parser's filename slug, never rename IDs in SQLite."""
    indexed = paper_ids(data)
    for item in manifest['files']:
        if item['status'] == 'duplicate' and item.get('duplicate_of'):
            canonical_duplicate = slug(item['duplicate_of'])
            if canonical_duplicate in indexed:
                item['duplicate_of'] = canonical_duplicate
        if not item.get('filename') or not item.get('paper_id'):
            continue
        canonical = slug(Path(item['filename']).stem)
        if canonical != item['paper_id']:
            item.setdefault('original_import_id', item['paper_id'])
            item['paper_id'] = canonical
        if item['status'] != 'failed':
            continue
        if canonical in indexed:
            # Older versions removed the live PDF after mistaking a slug
            # mismatch for a conversion failure. Its staging copy is intact.
            destination = data / 'papers' / item['filename']
            if not destination.exists():
                os.link(job / 'pdfs' / item['filename'], destination)
            item['status'] = 'indexed'
        elif duplicate := find_content_duplicate(data, item, indexed):
            item.update(status='duplicate', duplicate_of=duplicate)
        else:
            continue
        item['previous_error'] = item.pop('error', '')
    save_json(job / 'manifest.json', manifest)


def run_index_batch(session, url, data, manifest):
    def status():
        response = session.get(url + '/api/rag/ingest/status', timeout=15)
        response.raise_for_status()
        return response.json()
    while status().get('running'):
        progress(data, manifest, 'indexing', 'Waiting for the current LabUI index batch to finish')
        time.sleep(5)
    # Recheck cached chunks too: a reboot can interrupt embedding after the
    # paper's metadata row has been inserted but before its vectors are complete.
    response = session.post(url + '/api/rag/ingest/run', params={'force': 'true'}, timeout=30)
    if response.status_code != 409:
        response.raise_for_status()
    time.sleep(1)
    last_report = 0
    while True:
        state = status()
        if not state.get('running'):
            return state
        if time.monotonic() - last_report >= 15:
            indexed = paper_ids(data)
            cached = sum((data / 'rag/parsed' / (item.get('paper_id', '') + '.json')).exists()
                         for item in manifest['files'] if item['status'] == 'ready')
            count = sum(item.get('paper_id') in indexed for item in manifest['files'] if item['status'] in {'indexed', 'ready'})
            progress(data, manifest, 'indexing', f"Library import: {count} papers searchable; {cached} PDFs parsed in the current batch", searchable=count)
            last_report = time.monotonic()
        time.sleep(5)


def import_batches(data, job, manifest, url, batch_size):
    reconcile_manifest(data, job, manifest)
    session = requests.Session()
    session.trust_env = False
    session.headers['Connection'] = 'close'
    session.mount('http://', HTTPAdapter(max_retries=Retry(
        total=4, backoff_factor=1, status_forcelist=[502, 503, 504], allowed_methods={'GET', 'POST'},
    )))
    papers = data / 'papers'
    papers.mkdir(parents=True, exist_ok=True)
    while True:
        pending = [item for item in manifest['files'] if item['status'] in {'staged', 'ready'}]
        if not pending:
            break
        batch = pending[:batch_size]
        for item in batch:
            destination = papers / item['filename']
            if not destination.exists():
                os.link(job / 'pdfs' / item['filename'], destination)
            item['status'] = 'ready'
        save_json(job / 'manifest.json', manifest)
        for attempt in range(3):
            outcome = run_index_batch(session, url, data, manifest)
            indexed = paper_ids(data)
            if all(item.get('paper_id') not in indexed and not (data / 'rag/parsed' / (item['paper_id'] + '.json')).exists()
                   for item in batch if item['status'] == 'ready'):
                raise RuntimeError(f"No PDFs in this batch could be parsed. {outcome.get('message', '')}")
            remaining = []
            for item in batch:
                if item['status'] != 'ready':
                    continue
                if item['paper_id'] in indexed and outcome.get('last_returncode') == 0:
                    item['status'] = 'indexed'
                elif duplicate := find_content_duplicate(data, item, indexed):
                    item.update(status='duplicate', duplicate_of=duplicate)
                    (papers / item['filename']).unlink(missing_ok=True)
                elif (data / 'rag/parsed' / (item['paper_id'] + '.json')).exists():
                    remaining.append(item)
                else:
                    message = outcome.get('message', '')
                    if outcome.get('last_returncode') == 0:
                        message = 'No parsed text or indexed paper found after the index run'
                    item.update(status='failed', error=message or 'No readable text was extracted')
                    (papers / item['filename']).unlink(missing_ok=True)
            save_json(job / 'manifest.json', manifest)
            if not remaining:
                break
        if remaining:
            raise RuntimeError(f"Indexing did not finish: {outcome.get('message', 'unknown error')}")
    manifest['complete'] = True
    save_json(job / 'manifest.json', manifest)
    progress(data, manifest, 'complete', f"Library import finished: {counts(manifest)}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--data-dir', type=Path, required=True)
    parser.add_argument('--url', default='http://127.0.0.1:8770')
    parser.add_argument('--batch-size', type=int, default=10)
    parser.add_argument('--prepare-only', action='store_true')
    parser.add_argument('--retry-failed', action='store_true', help='Retry failed PDFs from the preserved staging copies')
    args = parser.parse_args()
    if args.batch_size < 1:
        parser.error('Batch size must be positive')
    data = args.data_dir.resolve()
    source = args.source.resolve()
    job = data / 'imports' / hashlib.sha256(str(source).encode()).hexdigest()[:12]
    job.mkdir(parents=True, exist_ok=True)
    with (data / 'imports/import.lock').open('w') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        manifest_file = job / 'manifest.json'
        manifest = json.loads(manifest_file.read_text()) if manifest_file.exists() else {
            'source': str(source), 'total': 0, 'files': [],
        }
        try:
            prepare(source, data, job, manifest)
            if not args.prepare_only:
                reconcile_manifest(data, job, manifest)
                if args.retry_failed:
                    for item in manifest['files']:
                        if item['status'] == 'failed' and item.get('filename'):
                            item['status'] = 'staged'
                    manifest['complete'] = False
                import_batches(data, job, manifest, args.url.rstrip('/'), args.batch_size)
        except Exception as exc:
            progress(data, manifest, 'error', f'Library import stopped: {exc}')
            raise


if __name__ == '__main__':
    main()
