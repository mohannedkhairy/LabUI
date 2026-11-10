"""Failed OCR vector installation must leave the original passages searchable."""
import sqlite3
import tempfile
from pathlib import Path
import unittest
from unittest.mock import patch

import numpy as np

from tools import repair_paper_text as repair


class PaperTextRepairTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.conn = repair.open_index(Path(temp.name) / 'rag.sqlite')
        self.addCleanup(self.conn.close)
        self.conn.executescript('''CREATE TABLE papers(paper_id TEXT PRIMARY KEY,title TEXT,summary TEXT);
            CREATE TABLE chunks(chunk_id TEXT PRIMARY KEY,paper_id TEXT,section_name TEXT,page_start INTEGER,page_end INTEGER,position INTEGER,text TEXT);
            CREATE VIRTUAL TABLE chunks_vec USING vec0(chunk_id TEXT PRIMARY KEY, embedding FLOAT[2]);
            CREATE VIRTUAL TABLE chunks_fts USING fts5(chunk_id UNINDEXED,text,content='chunks',content_rowid='rowid');
            INSERT INTO papers VALUES('p','Curated title','Preserved summary');
            INSERT INTO chunks VALUES('old','p','Body',1,1,0,'Uncorrected source text');''')
        self.conn.execute('INSERT INTO chunks_vec VALUES(?,?)', ('old', np.array([1, 0], dtype=np.float32).tobytes()))
        self.conn.execute("INSERT INTO chunks_fts(chunks_fts) VALUES('rebuild')")
        self.conn.commit()
        self.parsed = {'paper_id': 'p', 'title': 'Printed title', 'sections': [{'name': 'Body', 'text': 'Corrected readable source text.', 'page_start': 1, 'page_end': 1}]}
        for target, name, value in [(repair, 'profile', lambda: {'dimensions': 2}), (repair, 'ensure_compatible', lambda conn: None)]:
            mock = patch.object(target, name, value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_success_preserves_paper_metadata_and_searches_corrected_text(self):
        self.assertEqual(repair.replace_text(self.conn, self.parsed, [[0, 1]]), 1)
        self.assertEqual(tuple(self.conn.execute('SELECT * FROM papers').fetchone()), ('p', 'Curated title', 'Preserved summary'))
        self.assertEqual(self.conn.execute('SELECT text FROM chunks').fetchone()[0], 'Corrected readable source text.')
        self.assertEqual(self.conn.execute("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Corrected'").fetchone()[0], 1)

    def test_vector_write_failure_rolls_back_chunks_vectors_and_fts(self):
        with patch.object(repair, '_insert_vec', side_effect=RuntimeError('Vector write failure')):
            with self.assertRaisesRegex(RuntimeError, 'Vector write failure'):
                repair.replace_text(self.conn, self.parsed, [[0, 1]])
        self.assertEqual(self.conn.execute('SELECT chunk_id,text FROM chunks').fetchone()[0], 'old')
        self.assertEqual(self.conn.execute('SELECT chunk_id FROM chunks_vec').fetchone()[0], 'old')
        self.assertEqual(self.conn.execute("SELECT count(*) FROM chunks_fts WHERE chunks_fts MATCH 'Uncorrected'").fetchone()[0], 1)

    def test_bad_vector_or_unreadable_ocr_is_rejected_before_deletion(self):
        for vectors in [[[float('nan'), 1]], [[1]], [[0, 0]]]:
            with self.subTest(vectors=vectors), self.assertRaises(ValueError):
                repair.replace_text(self.conn, self.parsed, vectors)
        with self.assertRaisesRegex(ValueError, 'readable'):
            repair.replace_text(self.conn, dict(self.parsed, sections=[{'text': '\ufffd' * 300}]), [[0, 1]])
        self.assertEqual(self.conn.execute('SELECT chunk_id FROM chunks').fetchone()[0], 'old')


if __name__ == '__main__':
    unittest.main()
