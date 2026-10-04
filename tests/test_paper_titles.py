"""Metadata repair must change labels while preserving paper identity."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag' / 'rag'))
from paper_titles import reconcile_titles


class PaperTitleTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.db = self.root / 'rag.db'
        self.library = self.root / 'papers_library.json'
        with sqlite3.connect(self.db) as c:
            c.execute('CREATE TABLE papers(paper_id TEXT PRIMARY KEY,title TEXT,source_pdf TEXT,title_original TEXT,doi TEXT)')
            c.execute('CREATE TABLE citation_catalog(paper_id TEXT,title TEXT)')
            c.execute("INSERT INTO papers VALUES('123','123','/papers/123.pdf',NULL,'10.123/test')")
            c.execute("INSERT INTO citation_catalog VALUES('123','123')")

    def title(self):
        with sqlite3.connect(self.db) as c:
            return c.execute('SELECT title FROM papers').fetchone()[0]

    def test_repair_from_card_and_keep_stable_id(self):
        self.library.write_text(json.dumps([{'filename':'123.pdf','title':'Stability of aqueous nanobubbles'}]))
        self.assertEqual(reconcile_titles(self.db,self.library),1)
        self.assertEqual(self.title(),'Stability of aqueous nanobubbles')
        with sqlite3.connect(self.db) as c:
            self.assertEqual(c.execute('SELECT paper_id,title_original FROM papers').fetchone(),('123','123'))
            self.assertEqual(c.execute('SELECT title FROM citation_catalog').fetchone()[0],self.title())
        self.assertEqual(reconcile_titles(self.db,self.library),0)

    def test_keep_curated_title(self):
        with sqlite3.connect(self.db) as c:
            c.execute("UPDATE papers SET title='User corrected title'")
        self.library.write_text(json.dumps([{'filename':'123.pdf','title':'Different metadata title'}]))
        self.assertEqual(reconcile_titles(self.db,self.library),0)
        self.assertEqual(self.title(),'User corrected title')

    def test_missing_or_ambiguous_metadata_never_invents_a_title(self):
        self.assertEqual(reconcile_titles(self.db),0)
        self.library.write_text(json.dumps([{'filename':'123.pdf','title':'First plausible title'},{'filename':'123.pdf','title':'Second plausible title'}]))
        self.assertEqual(reconcile_titles(self.db,self.library),0)
        self.assertEqual(self.title(),'123')

    def test_parsed_card_recovers_by_exact_paper_id(self):
        parsed = self.root / 'parsed'
        parsed.mkdir()
        (parsed/'123.json').write_text(json.dumps({'paper_id':'123','title':'Bubble dynamics in aqueous media'}))
        self.assertEqual(reconcile_titles(self.db,parsed_dir=parsed),1)
        self.assertEqual(self.title(),'Bubble dynamics in aqueous media')


class MetadataIdentityTests(unittest.TestCase):
    def test_filename_match_must_be_exact_not_a_numeric_substring(self):
        from ingest.metadata import match
        self.assertIsNone(match(Path('/papers/12.pdf'), '12', [{'path':'/papers/312.pdf','title':'An unrelated scientific study'}]))
        self.assertEqual(match(Path('/papers/12.pdf'), '12', [{'path':'/papers/12.pdf','title':'Verified scientific study'}])['title'], 'Verified scientific study')
