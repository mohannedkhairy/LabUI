"""Preview or apply first-author/year citation keys, preserving IDs and aliases."""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))

import citations


def migrate(db: Path, audit: Path, *, apply=False):
    db = db.resolve()
    if not db.is_file():
        raise ValueError('Citation database does not exist')
    audit.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as source:
        source.row_factory = sqlite3.Row
        plan = citations.plan_author_year_keys(source)
        before = [tuple(row) for row in source.execute('SELECT * FROM papers ORDER BY paper_id')]
        catalog_before = [dict(row) for row in source.execute('SELECT * FROM citation_catalog ORDER BY paper_id')]
        backup = None
        if apply:
            backup = audit / ('before-citation-keys-' + datetime.now(UTC).strftime('%Y%m%dT%H%M%S%fZ') + '.sqlite')
            with sqlite3.connect(backup) as target:
                source.backup(target)
            backup.chmod(0o600)
    (audit / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2))
    result = {'planned': len(plan), 'applied': False, 'backup': str(backup) if backup else None}
    if apply:
        original_path = citations.DB_PATH
        try:
            citations.DB_PATH = db
            citations.sync_rag_papers(force=True)
        finally:
            citations.DB_PATH = original_path
        with sqlite3.connect(db.as_uri() + '?mode=ro', uri=True) as conn:
            conn.row_factory = sqlite3.Row
            after = [tuple(row) for row in conn.execute('SELECT * FROM papers ORDER BY paper_id')]
            if before != after:
                raise RuntimeError('Library paper rows changed unexpectedly; inspect the backup')
            rows_after = [dict(row) for row in conn.execute('SELECT * FROM citation_catalog')]
            by_paper = {row['paper_id']: row for row in rows_after if row['paper_id']}
            by_token = {row['citation_key']: row for row in rows_after}
            for row in rows_after:
                for alias in json.loads(row['aliases_json']):
                    by_token.setdefault(alias, row)
            renamed = 0
            for row in catalog_before:
                current = by_paper[row['paper_id']] if row['paper_id'] else by_token[row['citation_key']]
                if row['citation_key'] != current['citation_key'] and row['citation_key'] not in json.loads(current['aliases_json']):
                    raise RuntimeError('A legacy citation key was not preserved')
                renamed += row['citation_key'] != current['citation_key']
            result.update(applied=True, library_rows_preserved=len(before), catalog_rows=len(rows_after), renamed=renamed)
    (audit / 'result.json').write_text(json.dumps(result, indent=2))
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--db', required=True, type=Path)
    parser.add_argument('--audit', required=True, type=Path)
    parser.add_argument('--apply', action='store_true')
    args = parser.parse_args()
    print(json.dumps(migrate(args.db, args.audit, apply=args.apply), indent=2))


if __name__ == '__main__':
    main()
