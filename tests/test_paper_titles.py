"""Metadata repair must change labels while preserving paper identity."""
import json
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag' / 'rag'))
from paper_titles import reconcile_titles, verified_pdf_title


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

    def pdf(self, title, visible_title):
        import pymupdf
        path = self.root/'123.pdf'
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((50, 60), visible_title, fontsize=12)
            document.set_metadata({'title': title})
            document.save(path)
        with sqlite3.connect(self.db) as conn:
            conn.execute('UPDATE papers SET source_pdf=?', (str(path),))
        return path

    def test_recovers_pdf_title_and_preserves_identity_and_file(self):
        title = 'Stability of aqueous nanobubbles'
        path = self.pdf(title, title)
        original_bytes = path.read_bytes()
        self.assertEqual(reconcile_titles(self.db), 1)
        self.assertEqual(self.title(), title)
        self.assertEqual(path.read_bytes(), original_bytes)
        with sqlite3.connect(self.db) as conn:
            self.assertEqual(conn.execute('SELECT paper_id,title_original FROM papers').fetchone(), ('123','123'))
            self.assertEqual(conn.execute('SELECT title FROM citation_catalog').fetchone()[0], title)
        self.assertEqual(reconcile_titles(self.db), 0)

    def test_metadata_from_another_paper_is_rejected(self):
        path = self.pdf('A completely unrelated scientific article', 'Stability of aqueous nanobubbles')
        self.assertIsNone(verified_pdf_title(path))
        self.assertEqual(reconcile_titles(self.db), 0)

    def test_title_can_span_multiple_lines(self):
        path = self.pdf('Stability of aqueous nanobubbles', 'Stability of aqueous\nnanobubbles')
        self.assertEqual(verified_pdf_title(path), 'Stability of aqueous nanobubbles')

    def test_embedded_generic_title_and_curated_title_are_preserved(self):
        self.pdf('Untitled', 'Untitled\nStability of aqueous nanobubbles')
        self.assertEqual(reconcile_titles(self.db), 0)
        self.pdf('Stability of aqueous nanobubbles', 'Stability of aqueous nanobubbles')
        with sqlite3.connect(self.db) as conn:
            conn.execute("UPDATE papers SET title='User corrected title'")
        self.assertEqual(reconcile_titles(self.db), 0)
        self.assertEqual(self.title(), 'User corrected title')

    def test_cached_summary_also_recovers_title_without_a_model_call(self):
        from generation.summarize import summarize_paper
        from unittest.mock import patch
        title = 'Stability of aqueous nanobubbles'
        self.pdf(title, title)
        with sqlite3.connect(self.db) as conn:
            conn.execute('ALTER TABLE papers ADD COLUMN summary TEXT')
            conn.execute("UPDATE papers SET summary='An existing paper summary.'")
            conn.commit()
            with patch('generation.summarize.summarize_with_llm') as generate:
                self.assertEqual(summarize_paper(conn, '123', ''), 'An existing paper summary.')
                generate.assert_not_called()
        self.assertEqual(self.title(), title)

    def test_visible_title_with_no_metadata_requires_prominence_and_a_byline(self):
        import pymupdf
        path = self.root / 'cover.pdf'
        title = 'Thermodynamic Modeling of Aqueous Nanobubble Dispersion'
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((50, 60), 'Thermodynamic Modeling of Aqueous', fontsize=20)
            page.insert_text((50, 85), 'Nanobubble Dispersion', fontsize=20)
            page.insert_text((50, 115), 'Ada Lovelace, Alan Turing, and Grace Hopper', fontsize=10)
            page.insert_text((50, 140), 'Department of Science, University of Example', fontsize=9)
            page.insert_text((50, 170), 'Abstract', fontsize=10)
            page.insert_text((50, 190), 'This paper studies nanobubble stability in water.', fontsize=9)
            document.save(path)
        self.assertEqual(verified_pdf_title(path), title)
        from ingest.metadata import verified_pdf_authors
        self.assertEqual(verified_pdf_authors(path), ['Ada Lovelace', 'Alan Turing', 'Grace Hopper'])

    def test_document_creator_title_falls_back_to_visible_title(self):
        import pymupdf
        path = self.root / 'word.pdf'
        title = 'A study of nanobubble stability in aqueous solutions'
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((50, 60), title, fontsize=18)
            page.insert_text((50, 90), 'Ada Lovelace and Alan Turing', fontsize=10)
            page.insert_text((50, 120), 'Abstract: This paper reports stability measurements.', fontsize=9)
            document.set_metadata({'title': 'Microsoft Word - SPE-12345-MS'})
            document.save(path)
        self.assertEqual(verified_pdf_title(path), title)

    def test_truncated_publisher_tag_is_extended_from_the_visible_title(self):
        import pymupdf
        path = self.root / '123.pdf'
        prefix = 'Generation methods, stability and detection of bulk nanobubbles'
        full = prefix + ' in agro-food industries: a review and future perspective'
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((40, 60), prefix, fontsize=14)
            page.insert_text((40, 80), 'in agro-food industries: a review and future perspective', fontsize=14)
            page.insert_text((40, 110), 'Ada Lovelace and Alan Turing', fontsize=10)
            page.insert_text((40, 140), 'Department of Science, University of Example', fontsize=9)
            page.insert_text((40, 170), 'Abstract: Scientific measurements are described.', fontsize=9)
            document.set_metadata({'title': prefix})
            document.save(path)
        self.assertEqual(verified_pdf_title(path), full)
        with sqlite3.connect(self.db) as conn:
            conn.execute('UPDATE papers SET title=?,source_pdf=?', (prefix, str(path)))
            conn.commit()
            from paper_titles import apply_recovered_title
            self.assertTrue(apply_recovered_title(conn, '123', full))
            self.assertEqual(conn.execute('SELECT title FROM papers').fetchone()[0], full)

    def test_smaller_second_line_is_part_of_an_uppercase_title(self):
        import pymupdf
        path = self.root / 'shrinking.pdf'
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((40, 60), 'INFLUENCE OF LIQUID FLOWRATE ON NANOBUBBLES', fontsize=17)
            page.insert_text((40, 85), 'GENERATED BY POROUS MEMBRANE MODULES', fontsize=14)
            page.insert_text((40, 125), 'Ada Lovelace and Alan Turing', fontsize=12)
            page.insert_text((40, 155), 'Department of Science, University of Example', fontsize=10)
            page.insert_text((40, 190), 'Measurements of bubble sizes in flowing water.', fontsize=10)
            document.save(path)
        self.assertEqual(verified_pdf_title(path), 'INFLUENCE OF LIQUID FLOWRATE ON NANOBUBBLES GENERATED BY POROUS MEMBRANE MODULES')


class MetadataIdentityTests(unittest.TestCase):
    def test_filename_match_must_be_exact_not_a_numeric_substring(self):
        from ingest.metadata import match
        self.assertIsNone(match(Path('/papers/12.pdf'), '12', [{'path':'/papers/312.pdf','title':'An unrelated scientific study'}]))
        self.assertEqual(match(Path('/papers/12.pdf'), '12', [{'path':'/papers/12.pdf','title':'Verified scientific study'}])['title'], 'Verified scientific study')
