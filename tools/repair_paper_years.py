"""Preview/backfill missing publication years without rebuilding the library."""
import argparse
from collections import defaultdict, Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
from urllib.parse import quote
from uuid import uuid4

import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
from paper_years import pdf_text, text_year, record_year, matching_record, apply_year, _fold
from ingest.doi_metadata import pdf_dois
from tools.import_pdfs import save_json


def fetch_records(dois, cache):
    records = []
    with requests.Session() as session:
        session.trust_env = False
        session.headers['User-Agent'] = 'LabUI/1.0 (publication-year metadata repair)'
        for doi in dois:
            destination = cache / (hashlib.sha256(doi.encode()).hexdigest() + '.json')
            try:
                if destination.exists():
                    record = json.loads(destination.read_text())
                else:
                    response = session.get('https://api.crossref.org/works/' + quote(doi, safe=''), timeout=15)
                    if response.status_code in (400, 404):
                        record = {}
                    else:
                        response.raise_for_status()
                        record = response.json()['message']
                    temporary = destination.with_suffix('.' + uuid4().hex + '.tmp')
                    temporary.write_text(json.dumps(record, ensure_ascii=False))
                    temporary.replace(destination)
                records.append(record)
            except (requests.RequestException, OSError, ValueError, KeyError):
                continue
    return records


def choose_record(records, paper, dois):
    matches = []
    for record in records:
        if matching_record(record, paper['title'], paper['authors'], dois):
            evidence = record_year(record)
            if evidence:
                matches.append(dict(evidence, doi=record.get('DOI'), title=record.get('title')))
    return matches[0] if matches and len({r['year'] for r in matches}) == 1 else None


def run(db, audit, caches=(), fetch=False, apply=False):
    if not db.is_file():
        raise ValueError('Library index does not exist')
    audit.mkdir(parents=True, exist_ok=True)
    cache = audit / 'crossref'
    cache.mkdir(exist_ok=True)
    by_title, by_doi = defaultdict(list), {}
    for directory in [cache, *caches]:
        for file in directory.glob('*.json'):
            try:
                record = json.loads(file.read_text())
                if record.get('DOI'):
                    by_doi[record['DOI'].lower()] = record
                if record.get('title'):
                    by_title[_fold(record['title'][0])].append(record)
            except (OSError, ValueError, TypeError, AttributeError):
                continue
    conn = sqlite3.connect(db, timeout=30)
    conn.row_factory = sqlite3.Row
    rows = [dict(r) for r in conn.execute('SELECT paper_id,title,authors,year,doi,source_pdf FROM papers WHERE year IS NULL')]
    if apply:
        backup = audit / ('before-years-' + datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ') + '.sqlite')
        with sqlite3.connect(backup) as target:
            conn.backup(target)
        backup.chmod(0o600)
    results = []

    def install(paper, evidence):
        result = dict(paper_id=paper['paper_id'], title=paper['title'], evidence=evidence)
        if apply and evidence:
            with conn:
                apply_year(conn, paper['paper_id'], evidence)
        results.append(result)
        save_json(audit / 'results.json', results)
        if len(results) % 50 == 0 or len(results) == len(rows):
            print(f"Checked {len(results)}/{len(rows)}; {sum(bool(r['evidence']) for r in results)} years recovered", flush=True)

    try:
        with ThreadPoolExecutor(max_workers=3) as pool:
            pending = {}
            for paper in rows:
                path = db.parent / 'parsed' / (paper['paper_id'] + '.json')
                parsed = json.loads(path.read_text()) if path.exists() else None
                text = pdf_text(paper['source_pdf'], parsed)
                evidence = text_year(text, strong_only=True)
                if evidence:
                    install(paper, evidence)
                    continue
                records = by_title.get(_fold(paper['title']), [])
                evidence = choose_record(records, paper, [])
                if evidence:
                    install(paper, evidence)
                    continue
                dois = pdf_dois(paper['source_pdf'])
                if paper['doi'] and paper['doi'].lower() not in dois:
                    dois.insert(0, paper['doi'].lower())
                evidence = choose_record([by_doi[d] for d in dois if d in by_doi], paper, dois)
                fallback = text_year(text)
                if not evidence and fetch and any(d not in by_doi for d in dois):
                    future = pool.submit(fetch_records, [d for d in dois if d not in by_doi], cache)
                    pending[future] = (paper, dois, fallback)
                else:
                    install(paper, evidence or fallback)
            for future in as_completed(pending):
                paper, dois, fallback = pending[future]
                install(paper, choose_record(future.result(), paper, dois) or fallback)
        stats = {'total': len(rows), 'recovered': sum(bool(r['evidence']) for r in results),
                 'sources': dict(Counter(r['evidence']['source'] for r in results if r['evidence'])),
                 'unresolved': [dict(paper_id=r['paper_id'], title=r['title']) for r in results if not r['evidence']]}
        save_json(audit / 'status.json', stats)
        print(json.dumps({k: v if k != 'unresolved' else len(v) for k, v in stats.items()}), flush=True)
        return stats
    finally:
        conn.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--existing-cache', action='append', type=Path, default=[])
    parser.add_argument('--fetch-doi', action='store_true')
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    run(args.db, args.audit, args.existing_cache, args.fetch_doi, args.apply)
