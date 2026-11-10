"""A bulk import preserves originals, resumes, and isolates failed PDFs."""
import json
import sqlite3
import tempfile
import unittest
import threading
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch

import pymupdf

from tools import import_pdfs as bulk


class BulkImportTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.source = self.root / 'source'
        self.source.mkdir()
        self.data = self.root / 'data'
        (self.data / 'papers').mkdir(parents=True)
        (self.data / 'rag/parsed').mkdir(parents=True)
        self.job = self.data / 'imports/job'
        self.job.mkdir(parents=True)
        self.manifest = {'source': str(self.source), 'total': 0, 'files': []}

    def pdf(self, destination, text):
        destination.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open() as document:
            document.new_page().insert_text((72,72), text)
            document.save(destination)

    def test_exact_duplicates_invalid_pdf_and_colliding_names(self):
        self.pdf(self.source / 'a/paper.pdf', 'One paper')
        self.pdf(self.source / 'b/paper.pdf', 'A different paper')
        (self.source / 'duplicate.PDF').write_bytes((self.source / 'a/paper.pdf').read_bytes())
        (self.source / 'invalid.pdf').write_bytes(b'Unreadable PDF')
        before = {p: bulk.fingerprint(p) for p in self.source.rglob('*.pdf')}
        bulk.prepare(self.source, self.data, self.job, self.manifest)
        self.assertEqual(bulk.counts(self.manifest), {'staged': 2, 'duplicate': 1, 'invalid': 1})
        staged = list((self.job / 'pdfs').glob('*.pdf'))
        self.assertEqual(len(staged), 2)
        self.assertNotEqual(staged[0].name, staged[1].name)
        self.assertEqual(before, {p: bulk.fingerprint(p) for p in before})
        # A prepared import no longer depends on the original mount being present.
        bulk.prepare(self.root / 'unmounted', self.data, self.job, self.manifest)
        self.assertEqual(len(self.manifest['files']), 4)

    def test_existing_labui_pdf_is_not_copied_again(self):
        self.pdf(self.data / 'papers/existing.pdf', 'Already in LabUI')
        (self.source / 'another-name.pdf').write_bytes((self.data / 'papers/existing.pdf').read_bytes())
        bulk.prepare(self.source, self.data, self.job, self.manifest)
        self.assertEqual(bulk.counts(self.manifest), {'duplicate': 1})
        self.assertEqual(self.manifest['files'][0]['duplicate_of'], 'existing')

    def test_long_filename_id_agrees_with_parser_after_truncation(self):
        from ingest.parse_pdfs import _slug
        self.pdf(self.source / ('word_' * 24 + '.pdf'), 'A paper with a long filename')
        bulk.prepare(self.source, self.data, self.job, self.manifest)
        item = self.manifest['files'][0]
        self.assertEqual(item['paper_id'], _slug(Path(item['filename'])))
        self.assertNotIn('__', item['paper_id'])

    def test_old_slug_mismatch_restores_pdf_and_classifies_duplicate(self):
        for name in ['long__abc', 'copy__def']:
            self.pdf(self.job / 'pdfs' / (name + '.pdf'), name)
        with sqlite3.connect(self.data / 'rag/rag.db') as conn:
            conn.execute('CREATE TABLE papers(paper_id TEXT PRIMARY KEY)')
            conn.execute("INSERT INTO papers VALUES('long_abc')")
        (self.data / 'rag/parsed/long_abc.json').write_text(json.dumps({'sections': [{'text': 'The same complete paper text'}]}))
        (self.data / 'rag/parsed/copy_def.json').write_text(json.dumps({'sections': [{'text': 'The same complete paper text'}]}))
        self.manifest['files'] = [{'source': name, 'filename': name + '.pdf', 'paper_id': name,
                                  'status': 'failed', 'error': 'Indexed 5 papers'} for name in ['long__abc', 'copy__def']]
        bulk.reconcile_manifest(self.data, self.job, self.manifest)
        self.assertEqual(bulk.counts(self.manifest), {'indexed': 1, 'duplicate': 1})
        self.assertEqual(self.manifest['files'][0]['paper_id'], 'long_abc')
        self.assertTrue((self.data / 'papers/long__abc.pdf').exists())
        self.assertEqual(self.manifest['files'][1]['duplicate_of'], 'long_abc')
        self.assertNotIn('error', self.manifest['files'][0])

    def test_failed_conversion_does_not_block_good_papers(self):
        for name in ['good', 'unconvertible']:
            self.pdf(self.source / (name + '.pdf'), name)
        bulk.prepare(self.source, self.data, self.job, self.manifest)
        with sqlite3.connect(self.data / 'rag/rag.db') as conn:
            conn.execute('CREATE TABLE papers (paper_id TEXT PRIMARY KEY)')
        good, bad = self.manifest['files']
        calls = []
        def convert(*_):
            calls.append(True)
            (self.data / 'rag/parsed' / (good['paper_id'] + '.json')).write_text(json.dumps({'sections':[{'text':'Readable paper text'}]}))
            if len(calls) == 2:
                with sqlite3.connect(self.data / 'rag/rag.db') as conn:
                    conn.execute('INSERT INTO papers VALUES (?)', (good['paper_id'],))
            return {'message':'parse_pdfs failed' if len(calls) == 1 else 'Indexed', 'last_returncode': 1 if len(calls) == 1 else 0}
        with patch.object(bulk, 'run_index_batch', side_effect=convert):
            bulk.import_batches(self.data, self.job, self.manifest, 'http://test', 10)
        self.assertEqual(bulk.counts(self.manifest), {'indexed':1, 'failed':1})
        self.assertTrue((self.data / 'papers' / good['filename']).exists())
        self.assertFalse((self.data / 'papers' / bad['filename']).exists())
        self.assertTrue((self.job / 'pdfs' / bad['filename']).exists())
        self.assertTrue(self.manifest['complete'])

    def test_total_parser_failure_stops_before_skipping_entire_collection(self):
        self.pdf(self.source / 'paper.pdf', 'A real paper')
        bulk.prepare(self.source, self.data, self.job, self.manifest)
        with sqlite3.connect(self.data / 'rag/rag.db') as conn:
            conn.execute('CREATE TABLE papers (paper_id TEXT PRIMARY KEY)')
        with patch.object(bulk, 'run_index_batch', return_value={'message':'Parser dependency failed'}):
            with self.assertRaisesRegex(RuntimeError, 'No PDFs.*Parser dependency'):
                bulk.import_batches(self.data, self.job, self.manifest, 'http://test', 10)
        self.assertEqual(bulk.counts(self.manifest), {'ready':1})
        self.assertNotIn('complete', self.manifest)

    def test_resume_rechecks_a_paper_inserted_before_interrupted_embedding(self):
        self.pdf(self.source / 'paper.pdf', 'A real paper')
        bulk.prepare(self.source, self.data, self.job, self.manifest)
        item = self.manifest['files'][0]
        with sqlite3.connect(self.data / 'rag/rag.db') as conn:
            conn.execute('CREATE TABLE papers (paper_id TEXT PRIMARY KEY)')
            conn.execute('INSERT INTO papers VALUES (?)', (item['paper_id'],))
        with patch.object(bulk, 'run_index_batch', return_value={'last_returncode': 0}) as recheck:
            bulk.import_batches(self.data, self.job, self.manifest, 'http://test', 10)
        recheck.assert_called_once()
        self.assertEqual(item['status'], 'indexed')

    def test_force_ingest_repairs_cached_vectors_even_if_all_paper_rows_exist(self):
        from jfr.web import rag_routes
        self.pdf(self.data / 'papers/paper.pdf', 'A real paper')
        state = {}
        with patch.object(rag_routes, 'PAPERS_PDF_DIR', self.data / 'papers'), \
             patch.object(rag_routes, '_existing_paper_ids', return_value={'paper'}), \
             patch.object(rag_routes, '_list_pdf_files', return_value=[self.data / 'papers/paper.pdf']), \
             patch.object(rag_routes, '_index_run_lock', threading.Lock()), \
             patch.object(rag_routes, '_ingest_state', state), \
             patch.object(rag_routes.subprocess, 'run', return_value=SimpleNamespace(returncode=0, stdout='', stderr='')) as pipeline, \
             patch.object(rag_routes._summary_executor, 'submit'):
            rag_routes._trigger_ingest_once(force=True)
        self.assertEqual(pipeline.call_count, 2)
        self.assertEqual(state['last_returncode'], 0)
        self.assertFalse(state['running'])


if __name__ == '__main__':
    unittest.main()
