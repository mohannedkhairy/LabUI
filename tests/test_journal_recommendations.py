"""Rankings need actual evidence; failed refreshes must never look successful."""
import sqlite3
import tempfile
from pathlib import Path
from types import SimpleNamespace
import unittest
import threading
from unittest.mock import Mock, patch

import httpx

from jfr.db.schema import init_db
from jfr.config import Policy
from jfr.matching.engine import ManuscriptInput, recommend
from jfr.corpus import builder
from jfr.web import corpus_tasks


class JournalRankingTests(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.path = Path(temp.name) / 'jfr.sqlite'
        self.conn = init_db(self.path)
        self.addCleanup(self.conn.close)
        for jid, name, scope in [('surface', 'Surface Science', 'Colloids, interfaces, surface chemistry, nanobubbles and bubble stability in saline water.'),
                                  ('medicine', 'Retinal Genetics', 'Retinal disease, genetic mutations, human stem cells and regenerative medicine.')]:
            self.conn.execute('INSERT INTO journal(id,name,publisher,publisher_family,scope_statement) VALUES(?,?,?,?,?)', (jid, name, 'Publisher', 'publisher', scope))
        self.conn.commit()
        self.qdrant = Mock()
        self.qdrant.get_collection.side_effect = RuntimeError('No collection yet')

    def rank(self, text):
        return recommend(ManuscriptInput(text, text, text), self.conn, self.qdrant, Policy(), 'unused', 'unused')

    def test_empty_corpus_uses_labeled_scope_evidence_and_changes_with_query(self):
        with patch('jfr.corpus.embedder.embed_texts') as embed:
            bubbles = self.rank('Surface nanobubble stability in saline water')
            medicine = self.rank('Retinal disease and genetic mutations in human stem cells')
        embed.assert_not_called()
        self.assertEqual(bubbles[0].journal_id, 'surface')
        self.assertEqual(medicine[0].journal_id, 'medicine')
        self.assertGreater(bubbles[0].score, 0)
        self.assertEqual(bubbles[0].evidence_basis, 'scope')
        self.assertIn('no recent article corpus', bubbles[0].rationale)
        self.assertNotIn('moderate topical overlap', bubbles[0].rationale.lower())

    def test_article_text_is_ranked_before_vectors_are_ready_and_sources_are_visible(self):
        self.conn.execute("""INSERT INTO corpus_article(journal_id,doi,title,abstract,ingested_at)
            VALUES('surface','10.1234/example','Nanobubble salinity experiments',
            'Nanobubbles in saline water have surface charge and salt dependent stability.','2026-01-01')""")
        self.conn.commit()
        result = self.rank('Nanobubble surface charge and salinity dependent stability')[0]
        self.assertEqual(result.evidence_basis, 'article_text')
        self.assertEqual(result.corpus_articles, 1)
        self.assertEqual(result.nearest_articles[0]['doi'], '10.1234/example')

    def test_no_overlap_does_not_produce_arbitrary_numbered_rankings(self):
        results = self.rank('xyzzyquux')
        self.assertTrue(all(r.rank is None and r.evidence_basis == 'unavailable' for r in results))

    def test_broken_dense_model_still_reports_article_text_basis(self):
        self.conn.execute("""INSERT INTO corpus_article(journal_id,title,abstract,ingested_at)
            VALUES('surface','Nanobubbles','Nanobubbles in saline water and surface charge.','2026-01-01')""")
        self.conn.commit()
        self.conn.execute("UPDATE corpus_article SET vector_id=CAST(id AS TEXT),embedding_model='unused'")
        self.conn.commit()
        self.qdrant.get_collection.side_effect = None
        self.qdrant.get_collection.return_value = SimpleNamespace(points_count=3)
        with patch('jfr.corpus.embedder.embed_texts', side_effect=RuntimeError('Model offline')):
            result = self.rank('Nanobubbles in saline water')[0]
        self.assertEqual(result.evidence_basis, 'article_text')

    def test_recommendations_do_not_wait_for_background_vector_build(self):
        lock = threading.Lock()
        lock.acquire()
        with patch.object(corpus_tasks, '_vectors_lock', lock), patch('qdrant_client.QdrantClient') as client:
            with corpus_tasks.open_vectors(SimpleNamespace(vectors_dir=Path('/unused')), blocking=False) as vectors:
                self.assertIsNone(vectors)
            client.assert_not_called()
        self.assertTrue(lock.locked())
        lock.release()

    def test_merged_journal_keeps_its_history_but_is_not_a_submission_target(self):
        self.conn.execute('UPDATE journal SET metadata_json=? WHERE id=?',
                          ('{"active":false,"status_reason":"Incorporated into another journal"}', 'surface'))
        result = next(r for r in self.rank('Nanobubble surface stability') if r.journal_id == 'surface')
        self.assertFalse(result.policy.passed)
        self.assertIsNone(result.rank)
        self.assertIn('Incorporated', result.policy.reason)
        self.assertEqual(self.conn.execute("SELECT count(*) FROM journal WHERE id='surface'").fetchone()[0], 1)

    def test_refresh_with_no_articles_reports_failed_steps(self):
        self.conn.execute("UPDATE journal SET issn_electronic='1234-5678'")
        self.conn.commit()
        state = {}
        settings = SimpleNamespace(db_path=self.path, abstract_model='unused')
        with patch.object(corpus_tasks, 'get_settings', return_value=settings), \
             patch.object(corpus_tasks, '_state', state), \
             patch.object(corpus_tasks, 'open_vectors') as vectors, \
             patch('jfr.corpus.fetch_openalex_articles', return_value=[]), \
             patch('jfr.corpus.embed_corpus', return_value=0):
            vectors.return_value.__enter__.return_value = Mock()
            corpus_tasks._refresh_worker(limit=2)
        self.assertEqual(state['phase'], 'partial')
        self.assertEqual(len(state['errors']), 2)
        self.assertEqual(state['articles_added'], 0)
        self.assertFalse(state['running'])


class OpenAlexPagingTests(unittest.TestCase):
    def fetch(self, handler, limit=2):
        client = httpx.Client(transport=httpx.MockTransport(handler))
        with patch.object(builder.httpx, 'Client', return_value=client):
            return builder.fetch_openalex_articles('1234-5678', limit=limit)

    def test_basic_paging_does_not_use_restricted_cursor(self):
        calls = []
        def handler(request):
            calls.append(dict(request.url.params))
            page = int(request.url.params['page'])
            return httpx.Response(200, json={'meta': {'count': 4}, 'results': [{
                'doi': 'https://doi.org/10.1234/' + str(page), 'title': 'A real source title',
                'abstract_inverted_index': {'Scientific': [0], 'abstract': [1]},
                'publication_date': '2026-01-01'}]})
        articles = self.fetch(handler)
        self.assertEqual(len(articles), 2)
        self.assertEqual([p['page'] for p in calls], ['1', '2'])
        self.assertTrue(all('cursor' not in p and int(p['per-page']) <= 100 for p in calls))

    def test_later_network_failure_preserves_already_fetched_articles(self):
        def handler(request):
            if request.url.params['page'] == '2':
                return httpx.Response(401, json={'error': 'API key required'})
            return httpx.Response(200, json={'meta': {'count': 4}, 'results': [{
                'doi': 'https://doi.org/10.1234/first', 'abstract_inverted_index': {'Scientific': [0]}}]})
        with self.assertLogs('jfr.corpus.builder', level='WARNING'):
            articles = self.fetch(handler)
        self.assertEqual(articles[0]['doi'], '10.1234/first')

    def test_first_page_failure_is_not_reported_as_empty_success(self):
        with self.assertRaises(httpx.HTTPStatusError):
            self.fetch(lambda request: httpx.Response(401))


if __name__ == '__main__':
    unittest.main()
