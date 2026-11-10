"""Repair missing bibliographic labels with a resumable, evidence-checked audit.

Uses the app's existing model adapter only with --with-model. Existing curated
labels, IDs, citation keys, PDF files, chunks, vectors and summaries are retained.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from paper_titles import is_placeholder, verified_pdf_title, apply_recovered_title, parsed_header
from ingest.metadata import verified_pdf_authors
from ingest.header_metadata import pdf_headers, extract_header_metadata
from tools.import_pdfs import save_json


def _model_proposal(pid, headers, model, base_url, audit, dois=(), with_doi=False):
    from ingest.header_metadata import validate_header_metadata
    if with_doi:
        from ingest.doi_metadata import recover_doi_metadata
        record = recover_doi_metadata(dois, headers, audit / 'crossref')
        if record:
            return record
    if not model:
        return {'error': 'No DOI record matching the visible title and authors'}
    key = hashlib.sha256(json.dumps(['independent-title-v2', pid, model, headers], sort_keys=True).encode()).hexdigest()
    cache = audit / (key + '.json')
    try:
        if cache.exists():
            record = json.loads(cache.read_text())
            if 'error' in record:
                return {'error': record['error']}
            return validate_header_metadata(record['metadata'], headers)
        from retrieval.workload import wait_for_interactive
        wait_for_interactive()
        evidence = extract_header_metadata(headers, model, base_url)
        save_json(cache, {'paper_id': pid, 'metadata': evidence})
        return evidence
    except Exception as exc:
        save_json(cache, {'paper_id': pid, 'error': str(exc)})
        return {'error': str(exc)}


def run(db, audit, model='', base_url='http://127.0.0.1:11435', apply=False, workers=2, with_doi=False):
    if not db.is_file():
        raise ValueError('The library index does not exist')
    audit.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db, timeout=30)
    conn.row_factory = sqlite3.Row
    if apply:
        backup = audit / ('before-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.sqlite')
        with sqlite3.connect(backup) as target:
            conn.backup(target)
    papers = [dict(paper) for paper in conn.execute('SELECT paper_id,title,authors,source_pdf FROM papers')
              if is_placeholder(paper['title'], paper['paper_id'], paper['source_pdf']) or not (paper['authors'] or '').strip()]
    stats = {'running': True, 'total': len(papers), 'examined': 0, 'titles': 0, 'authors': 0, 'unresolved': []}
    catalog = bool(conn.execute("SELECT 1 FROM sqlite_master WHERE name='citation_catalog'").fetchone())

    def install(paper, title, authors, evidence):
        pid = paper['paper_id']
        missing_title = is_placeholder(paper['title'], pid, paper['source_pdf'])
        missing_authors = not (paper['authors'] or '').strip()
        if apply:
            if missing_title and title and apply_recovered_title(conn, pid, title):
                stats['titles'] += 1
            if missing_authors and authors:
                value = '; '.join(authors)
                changed = conn.execute("UPDATE papers SET authors=? WHERE paper_id=? AND trim(COALESCE(authors,''))=''", (value, pid)).rowcount
                if catalog and changed:
                    conn.execute('UPDATE citation_catalog SET authors=? WHERE paper_id=?', (value, pid))
                stats['authors'] += changed
            conn.commit()
        else:
            stats['titles'] += bool(missing_title and title)
            stats['authors'] += bool(missing_authors and authors)
        stats['examined'] += 1
        if (missing_title and not title) or (missing_authors and not authors):
            stats['unresolved'].append({'paper_id': pid, **evidence})
        save_json(audit / (pid + '.json'), {'paper_id': pid, 'title': title, 'authors': authors, 'evidence': evidence})
        save_json(audit / 'status.json', stats)
        print(json.dumps({k: v if k != 'unresolved' else len(v) for k, v in stats.items()}) + ' ' + pid, flush=True)

    try:
        # PDF libraries are used only by this thread. Workers handle independent
        # model requests; all SQLite writes remain on this thread as well.
        with ThreadPoolExecutor(max_workers=workers) as pool:
            pending = {}
            for paper in papers:
                missing_title = is_placeholder(paper['title'], paper['paper_id'], paper['source_pdf'])
                missing_authors = not (paper['authors'] or '').strip()
                title = verified_pdf_title(paper['source_pdf']) if missing_title else paper['title']
                authors = verified_pdf_authors(paper['source_pdf'], title) if missing_authors else []
                local_evidence = {'method': 'PDF metadata and layout'}
                cached = db.parent / 'parsed' / (paper['paper_id'] + '.json')
                if cached.exists() and ((missing_title and not title) or (missing_authors and not authors)):
                    record = json.loads(cached.read_text())
                    recovered = parsed_header(record)
                    if recovered and record.get('paper_id') == paper['paper_id']:
                        local_evidence = recovered
                        if missing_title and not title:
                            title = recovered['title']
                        if missing_authors and not authors:
                            authors = recovered['authors']
                if (model or with_doi) and ((missing_title and not title) or (missing_authors and not authors)):
                    try:
                        headers = pdf_headers(paper['source_pdf'])
                        from ingest.doi_metadata import pdf_dois
                        dois = pdf_dois(paper['source_pdf']) if with_doi else []
                    except Exception as exc:
                        install(paper, title, authors, {'error': str(exc)})
                        continue
                    future = pool.submit(_model_proposal, paper['paper_id'], headers, model, base_url, audit, dois, with_doi)
                    pending[future] = (paper, title, authors)
                else:
                    install(paper, title, authors, local_evidence)
            for future in as_completed(pending):
                paper, title, authors = pending[future]
                evidence = future.result()
                if 'error' not in evidence:
                    if is_placeholder(paper['title'], paper['paper_id'], paper['source_pdf']):
                        title = evidence['title']
                    if not (paper['authors'] or '').strip():
                        authors = evidence['authors']
                install(paper, title, authors, evidence)
        stats['running'] = False
        save_json(audit / 'status.json', stats)
        return stats
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--with-model', action='store_true')
    parser.add_argument('--with-doi', action='store_true', help='Verify public Crossref DOI metadata against PDF headers')
    parser.add_argument('--base-url', default='http://127.0.0.1:11435')
    parser.add_argument('--workers', type=int, choices=range(1, 5), default=2)
    args = parser.parse_args()
    from generation.summarize import resolve_gen_model
    model = resolve_gen_model(args.base_url) if args.with_model else ''
    if args.with_model and not model:
        raise SystemExit('No chat model available; no metadata changed')
    run(args.db, args.audit, model, args.base_url, args.apply, args.workers, args.with_doi)
