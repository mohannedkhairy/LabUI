"""Short keys, exact aliases, and writing exports must identify the same paper."""
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import citations
import writing
from fastapi import FastAPI
from fastapi.testclient import TestClient
from jfr.web.writing_routes import router


class CitationFixture(unittest.TestCase):
    def setUp(self):
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name)
        self.db = self.root / 'rag.db'
        self.writing_dir = self.root / 'manuscripts'
        for module, attribute, value in [
            (citations, 'DB_PATH', self.db), (writing, 'DB_PATH', self.db),
            (writing, 'MANUSCRIPTS_DB_PATH', self.root / 'manuscripts.db'),
            (writing, 'MANUSCRIPTS_DIR', self.writing_dir),
        ]:
            p = patch.object(module, attribute, value)
            p.start()
            self.addCleanup(p.stop)
        with sqlite3.connect(self.db) as conn:
            conn.execute('''CREATE TABLE papers (paper_id TEXT PRIMARY KEY,title TEXT,authors TEXT,year INTEGER,
                doi TEXT,journal TEXT,volume TEXT,issue TEXT,pages TEXT,publisher TEXT,url TEXT,abstract TEXT)''')
        citations.init_db()

    def paper(self, pid='cai-paper', authors='Liyuan Cai; Jingchun Wu', year=2024,
              title='Investigating CO2 nanobubbles for enhanced oil recovery', old_key=None, aliases=None):
        with sqlite3.connect(self.db) as conn:
            conn.execute('INSERT INTO papers(paper_id,title,authors,year) VALUES(?,?,?,?)', (pid,title,authors,year))
            if old_key:
                conn.execute('''INSERT INTO citation_catalog(citation_key,paper_id,title,authors,year,aliases_json,created_at,updated_at)
                    VALUES(?,?,?,?,?,?,1,1)''', (old_key,pid,title,authors,year,json.dumps(aliases or [pid])))

    def records(self):
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            return [dict(r) for r in conn.execute('SELECT * FROM citation_catalog ORDER BY paper_id')]


class CitationKeysTests(CitationFixture):
    def test_first_author_year_and_collision_letters(self):
        self.assertEqual(citations.make_key('Long title', 'Liyuan Cai; Jingchun Wu', 2024), 'cai2024')
        self.assertEqual(citations.make_key('Title', 'Cai, Liyuan and Wu, Jingchun', 2024), 'cai2024')
        self.assertEqual(citations.make_key('Title', 'Khairy et al.', 2025), 'khairy2025')
        self.assertEqual(citations.make_key('Title', 'Liyuan Cai', 2024, {'cai2024','cai2024a'}), 'cai2024b')
        taken = {'cai2024'} | {'cai2024'+chr(i) for i in range(97,123)}
        self.assertEqual(citations.make_key('Title', 'Liyuan Cai', 2024, taken), 'cai2024aa')

    def test_missing_metadata_uses_explicit_fallbacks(self):
        self.assertEqual(citations.make_key('Title', 'Liyuan Cai', None), 'caind')
        self.assertEqual(citations.make_key('Title', '', 2024), 'anon2024')
        self.assertEqual(citations.make_key('Title'), 'anonnd')

    def test_legacy_key_becomes_alias_without_changing_paper_or_metadata(self):
        self.paper(old_key='caiinvestigatingpotentialco2', aliases=['external-key','cai-paper'])
        with sqlite3.connect(self.db) as conn:
            before = conn.execute('SELECT * FROM papers').fetchall()
        citations.sync_rag_papers()
        record = self.records()[0]
        self.assertEqual(record['citation_key'], 'cai2024')
        self.assertEqual(set(json.loads(record['aliases_json'])), {'external-key','cai-paper','caiinvestigatingpotentialco2'})
        for token in ['cai2024','caiinvestigatingpotentialco2','external-key','cai-paper']:
            self.assertEqual(citations.resolve_key(token)['paper_id'], 'cai-paper')
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT * FROM papers').fetchall(), before)

    def test_planning_is_read_only_and_migration_is_idempotent(self):
        self.paper(old_key='old-cai')
        with sqlite3.connect(self.db) as conn:
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA query_only=ON')
            self.assertEqual(citations.plan_author_year_keys(conn)[0]['new_key'], 'cai2024')
        citations.sync_rag_papers()
        before = self.records()
        self.assertEqual(citations.sync_rag_papers(), 0)
        citations.sync_rag_papers(force=True)
        self.assertEqual(self.records()[0]['citation_key'], before[0]['citation_key'])
        self.assertEqual(self.records()[0]['aliases_json'], before[0]['aliases_json'])

    def test_different_papers_same_author_year_have_stable_unique_keys(self):
        self.paper(old_key='old-a')
        self.paper(pid='second', title='Another CO2 study', old_key='old-b')
        citations.sync_rag_papers()
        self.assertEqual({r['citation_key'] for r in self.records()}, {'cai2024','cai2024a'})
        before = {r['paper_id']:r['citation_key'] for r in self.records()}
        citations.sync_rag_papers(force=True)
        self.assertEqual({r['paper_id']:r['citation_key'] for r in self.records()}, before)

    def test_old_alias_cannot_be_reassigned_to_another_paper(self):
        self.paper(pid='other', authors='Ada Smith', old_key='old-smith', aliases=['cai2024'])
        self.paper(old_key='old-cai')
        citations.sync_rag_papers()
        self.assertEqual(citations.resolve_key('cai2024')['paper_id'], 'other')
        self.assertEqual(citations.resolve_key('cai2024a')['paper_id'], 'cai-paper')

    def test_corrected_author_or_year_refreshes_key_and_preserves_prior_key(self):
        self.paper(year=None)
        citations.sync_rag_papers()
        self.assertEqual(self.records()[0]['citation_key'], 'caind')
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE papers SET year=2024 WHERE paper_id='cai-paper'")
        citations.sync_rag_papers()
        self.assertEqual(citations.resolve_key('caind')['citation_key'], 'cai2024')
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE papers SET authors='Liyuan Chen' WHERE paper_id='cai-paper'")
        citations.sync_rag_papers()
        self.assertEqual(citations.resolve_key('cai2024')['citation_key'], 'chen2024')

    def test_alias_lookup_is_exact_not_a_like_wildcard(self):
        self.paper(old_key='old', aliases=['legacy_any'])
        citations.sync_rag_papers()
        self.assertIsNone(citations.resolve_key('legacy_%'))
        self.assertIsNone(citations.resolve_key('legacy_'))
        self.assertEqual(citations.resolve_key('legacy_any')['paper_id'], 'cai-paper')

    def test_bare_at_returns_suggestions_and_first_author_prefix_ranks_first(self):
        self.paper()
        self.paper(pid='coauthor', authors='Xuesong Zhang; Li Cai', year=2025)
        self.paper(pid='earlier', authors='Wen Bin Cai', year=2015)
        citations.sync_rag_papers()
        self.assertEqual(len(citations.catalog_search('')), 3)
        self.assertEqual(citations.catalog_search('@cai')[0]['citation_key'], 'cai2024')
        self.assertEqual(citations.catalog_search('c')[0]['citation_key'], 'cai2024')
        self.assertEqual(len(citations.catalog_search('CO2')), 3)

    def test_orphaned_smoke_fixture_never_appears_in_autocomplete(self):
        self.paper()
        with sqlite3.connect(self.db) as conn:
            conn.execute("""INSERT INTO citation_catalog(citation_key,paper_id,title,authors,year,created_at,updated_at)
                VALUES('fixture','missing','Smoke fixture','Cai',2026,1,1)""")
        citations.sync_rag_papers()
        self.assertEqual([r['paper_id'] for r in citations.catalog_search('cai')], ['cai-paper'])
        # An orphan must not make the catalog count mask a newly indexed paper.
        self.paper(pid='new', authors='New Author', year=2026)
        citations.sync_rag_papers()
        self.assertEqual(citations.resolve_key('author2026')['paper_id'], 'new')

    def test_autocomplete_api_accepts_empty_and_partial_queries(self):
        self.paper()
        app = FastAPI()
        app.include_router(router, prefix='/api/rag')
        with TestClient(app) as client:
            self.assertEqual(client.get('/api/rag/citations/autocomplete?q=').json()['citations'][0]['citation_key'], 'cai2024')
            self.assertEqual(client.get('/api/rag/citations/autocomplete?q=cai').json()['citations'][0]['paper_id'], 'cai-paper')

    def test_migration_tool_backs_up_and_preserves_aliases_and_library(self):
        from tools.migrate_citation_keys import migrate
        self.paper(old_key='old-cai')
        audit = self.root / 'audit'
        preview = migrate(self.db, audit)
        self.assertFalse(preview['applied'])
        self.assertEqual(self.records()[0]['citation_key'], 'old-cai')
        applied = migrate(self.db, audit, apply=True)
        self.assertTrue(Path(applied['backup']).is_file())
        with sqlite3.connect(applied['backup']) as conn:
            self.assertEqual(conn.execute('SELECT citation_key FROM citation_catalog').fetchone()[0], 'old-cai')
        self.assertEqual(applied['renamed'], 1)
        self.assertEqual(applied['library_rows_preserved'], 1)
        self.assertEqual(citations.resolve_key('old-cai')['citation_key'], 'cai2024')

    def test_old_and_new_tokens_resolve_once_and_export_with_same_number(self):
        self.paper(old_key='old-cai')
        citations.sync_rag_papers()
        conn = writing.new_conn()
        self.addCleanup(conn.close)
        project = writing.create_project(conn, title='Citations test')
        project_id = project['id'] if isinstance(project, dict) else project
        writing.create_file(conn, project_id, title='Introduction', slug='introduction')
        writing.update_file(conn, project_id, 'introduction', content='Evidence @old-cai and @cai2024. Contact user@example.com.')
        refs = writing.project_citations(conn, project_id)
        self.assertEqual(len(refs), 1)
        self.assertIn('old-cai', refs[0]['aliases'])
        output = writing.render_export_md(conn, project_id)
        self.assertIn('Evidence [1] and [1].', output)
        self.assertIn('user@example.com', output)
        self.assertIn('@article{cai2024,', writing.render_bibtex(refs))


if __name__ == '__main__':
    unittest.main()
