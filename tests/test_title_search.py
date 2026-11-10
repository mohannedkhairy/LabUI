"""Recovered metadata titles must help retrieval without modifying chunk text."""
import sqlite3
import sys
import unittest
from pathlib import Path
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag' / 'rag'))
from retrieval.search import _title_search
from retrieval.rerank import rerank


class TitleSearchTests(unittest.TestCase):
    def setUp(self):
        self.conn = sqlite3.connect(':memory:')
        self.addCleanup(self.conn.close)
        self.conn.row_factory = sqlite3.Row
        self.conn.executescript('''
            CREATE TABLE papers(paper_id TEXT,title TEXT);
            CREATE TABLE chunks(chunk_id TEXT,paper_id TEXT,position INT,text TEXT);
            INSERT INTO papers VALUES('a','Theoretical model of nanobubble stability');
            INSERT INTO papers VALUES('b','Experimental measurements of water quality');
            INSERT INTO chunks VALUES('a-1','a',0,'A passage without the title words.');
            INSERT INTO chunks VALUES('b-1','b',0,'Another passage.');
        ''')

    def test_title_terms_retrieve_a_passage_without_body_matches(self):
        self.assertEqual(_title_search(self.conn, 'Find the theoretical nanobubble model', 5), ['a-1'])

    def test_selected_paper_filter_applies_to_title_matches(self):
        self.assertEqual(_title_search(self.conn, 'theoretical model', 5, ['b']), [])

    def test_unrelated_title_and_empty_query_do_not_match(self):
        self.assertEqual(_title_search(self.conn, 'unrelated topic', 5), [])
        self.assertEqual(_title_search(self.conn, '?!', 5), [])

    def test_reranker_sees_the_canonical_title(self):
        model = Mock()
        model.predict.return_value = [1.0]
        chunks = [{'title': 'Recovered actual paper title', 'text': 'A body excerpt.'}]
        self.assertEqual(rerank(model, 'paper title', chunks, 1), chunks)
        self.assertIn('Recovered actual paper title', model.predict.call_args.args[0][0][1])


if __name__ == '__main__':
    unittest.main()
