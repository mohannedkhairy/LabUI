"""Small library-specific sanity check, not a reviewed retrieval benchmark.

Questions target four known papers. Records source ranks, source text and latency
for manual inspection. Selected-paper checks also detect accidental scope leaks.
No papers, conversations or indexes are modified.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import time

import requests


CASES = [
    ('1-s2_0-S0021979724019404-main',
     'How does a chemically heterogeneous surface influence nanobubble stability and contact-line pinning?'),
    ('1-s2_0-S0043135426011851-main',
     'How do pH and generation time influence electric-field-generated air nanobubble stability?'),
    ('044505_1_online_c02886b40cc8',
     'Which scaled charges and water model are used for the Madrid-2019 parameters for fluoride, bromide, iodide, rubidium, and cesium?'),
    ('059_spe-215122-pa_08dcba27da5f',
     'How is the GERG-2008 equation of state used to model the thermodynamic stability of aqueous nanobubble dispersions?'),
]


def run(base_url, label, destination):
    session = requests.Session()
    session.trust_env = False
    status = session.get(base_url + '/api/rag/status', timeout=30).json()
    report = {'label':label, 'created_at':datetime.now(timezone.utc).isoformat(),
              'limitation':'Four known-paper sanity checks, without reviewed passage relevance labels. Not evidence of general answer quality.',
              'settings':{key:status.get(key) for key in ('embed_model_name','embedding_provider','embed_dim',
                         'reranker_model_name','reranker_provider','papers','chunks')}, 'cases':[]}
    for paper_id, query in CASES:
        item = {'query':query, 'expected_paper_id':paper_id}
        for selected in (False, True):
            body = {'query':query, 'top_k':10}
            if selected:
                body['selected_paper_ids'] = [paper_id]
            started = time.monotonic()
            response = session.post(base_url + '/api/rag/search', json=body, timeout=240)
            response.raise_for_status()
            results = response.json()['results']
            ranks = [index for index, row in enumerate(results, 1) if row['paper_id'] == paper_id]
            item['scoped' if selected else 'library'] = {
                'seconds':round(time.monotonic()-started,2), 'expected_paper_rank':min(ranks) if ranks else None,
                'scope_valid':all(row['paper_id'] == paper_id for row in results) if selected else None,
                'results':[{key:row.get(key) for key in ('paper_id','chunk_id','title','section_name','page_start','page_end','text')} for row in results],
            }
        report['cases'].append(item)
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2))
        print(f"{paper_id}: library rank={item['library']['expected_paper_rank']}, scoped rank={item['scoped']['expected_paper_rank']}, scope valid={item['scoped']['scope_valid']}", flush=True)
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='http://127.0.0.1:8770')
    parser.add_argument('--label', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    run(args.base_url, args.label, args.output)
