"""Summary availability and failures must reflect saved results, across restarts."""
import sqlite3
import sys
import tempfile
from pathlib import Path
import threading
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
from generation import summarize as core
from jfr.web import rag_routes as routes


class SummaryPipelineTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db = self.root / 'rag.db'
        with sqlite3.connect(self.db) as conn:
            conn.executescript('''CREATE TABLE papers(paper_id TEXT PRIMARY KEY,title TEXT,source_pdf TEXT,summary TEXT);
                CREATE TABLE chunks(paper_id TEXT,section_name TEXT,text TEXT,position INTEGER);
                INSERT INTO papers VALUES('cached','Existing paper','', 'Existing summary');
                INSERT INTO papers VALUES('new','A new paper','', '');
                INSERT INTO papers VALUES('bad','An unreadable paper','', '');
                INSERT INTO chunks VALUES('new','Abstract','Readable source text',0);''')
        self.state = {}
        for name, value in [('DB_PATH', self.db), ('_open_db', lambda: sqlite3.connect(self.db)),
                            ('_summary_state', self.state), ('_summary_build_lock', threading.Lock())]:
            patcher = patch.object(routes, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def test_build_counts_only_saved_summaries_and_exposes_unfinished_papers(self):
        def generate(conn, pid, force=False):
            if pid == 'new':
                conn.execute("UPDATE papers SET summary='Generated summary' WHERE paper_id=?", (pid,))
                conn.commit()
                return 'Generated summary'
            return ''
        with patch.object(routes, 'resolve_gen_model', return_value='chat'), patch.object(routes, 'summarize_paper', side_effect=generate):
            routes._run_summary_build()
        status = routes.api_summaries_status()
        self.assertEqual((status['generated'], status['skipped'], status['failed']), (1, 1, 0))
        self.assertEqual((status['available'], status['library_total'], status['pending']), (2, 3, 1))
        self.assertEqual(status['missing'][0]['paper_id'], 'bad')
        self.assertNotIn('2 summary(ies)', status['message'])
        # A process restart loses run counters, but never the library totals.
        self.state.clear()
        self.assertEqual(routes.api_summaries_status()['available'], 2)

    def test_model_failures_are_not_reported_as_success(self):
        with patch.object(routes, 'resolve_gen_model', return_value='chat'), patch.object(routes, 'summarize_paper', side_effect=RuntimeError('Model offline')):
            routes._run_summary_build()
        self.assertEqual(self.state['failed'], 2)
        self.assertEqual(self.state['generated'], 0)
        self.assertFalse(self.state['running'])
        self.assertFalse(routes._summary_build_lock.locked())

    def test_sparse_text_records_a_durable_reason_without_calling_model(self):
        with sqlite3.connect(self.db) as conn, patch.object(core, 'summarize_with_llm') as model:
            self.assertEqual(core.summarize_paper(conn, 'bad', 'chat'), '')
            model.assert_not_called()
            status, error = conn.execute("SELECT status,error FROM paper_summary_attempts WHERE paper_id='bad'").fetchone()
            self.assertEqual(status, 'skipped')
            self.assertIn('Too little readable text', error)
        missing = {paper['paper_id']: paper for paper in routes.api_summaries_status()['missing']}
        self.assertIn('Too little readable text', missing['bad']['reason'])

    def test_model_exception_is_durable_and_preserves_cached_summaries(self):
        with sqlite3.connect(self.db) as conn, patch.object(core, 'gather_paper_text', return_value='Readable text. ' * 30), patch.object(core, 'summarize_with_llm', side_effect=RuntimeError('Remote server disconnected')):
            self.assertEqual(core.summarize_paper(conn, 'cached', 'chat'), 'Existing summary')
            with self.assertRaisesRegex(RuntimeError, 'disconnected'):
                core.summarize_paper(conn, 'new', 'chat')
            self.assertEqual(conn.execute("SELECT status FROM paper_summary_attempts WHERE paper_id='new'").fetchone()[0], 'failed')
            self.assertEqual(conn.execute("SELECT summary FROM papers WHERE paper_id='new'").fetchone()[0], '')

    def test_table_heavy_supplement_uses_real_pdf_text(self):
        import pymupdf
        path = self.root / 'supplement.pdf'
        with pymupdf.open() as document:
            page = document.new_page()
            for index in range(12):
                page.insert_text((50, 50 + index * 20), 'Force field parameters for zeolite and adsorbate interactions.')
            document.save(path)
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE papers SET source_pdf=? WHERE paper_id='new'", (str(path),))
            self.assertGreater(len(core.gather_paper_text(conn, 'new')), 200)
            self.assertIn('Force field parameters', core.gather_paper_text(conn, 'new'))

    def test_unfinished_reasoning_never_becomes_a_cached_summary(self):
        self.assertEqual(core.strip_think('<think>I need to reason about this paper'), '')
        self.assertEqual(core.strip_think('<think>Private reasoning</think>Actual summary.'), 'Actual summary.')


if __name__ == '__main__':
    unittest.main()
