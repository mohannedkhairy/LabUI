"""Recover complete bylines, preserve trusted metadata, and avoid guessing."""
import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import pymupdf

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag' / 'rag'))
from ingest.metadata import verified_pdf_authors, reconcile_authors
from ingest import parse_pdfs


class PaperAuthorTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.pdf = self.root/'paper.pdf'
        self.title = 'An experimental study of nanobubble stability'

    def make_pdf(self, hint='Ada Lovelace', byline='Ada Lovelace, Alan Turing', continuation=None):
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((50,60), self.title, fontsize=14)
            page.insert_text((50,90), byline, fontsize=11)
            if continuation:
                page.insert_text((300,90), continuation, fontsize=11)
            page.insert_text((50,110), 'Department of Science, University of Example', fontsize=8)
            page.insert_text((50,145), 'Abstract', fontsize=11)
            page.insert_text((50,165), 'Experimental measurements are described here.', fontsize=10)
            document.set_metadata({'title': self.title, 'author': hint})
            document.save(self.pdf)

    def database(self, authors=''):
        path = self.root/'rag.db'
        with sqlite3.connect(path) as conn:
            conn.execute('CREATE TABLE papers(paper_id TEXT,title TEXT,authors TEXT,source_pdf TEXT,summary TEXT)')
            conn.execute('CREATE TABLE citation_catalog(paper_id TEXT,citation_key TEXT,authors TEXT)')
            conn.execute('INSERT INTO papers VALUES(?,?,?,?,?)', ('stable-id',self.title,authors,str(self.pdf),'Existing summary'))
            conn.execute("INSERT INTO citation_catalog VALUES('stable-id','existing-key','')")
        return path

    def test_first_author_tag_does_not_truncate_full_byline(self):
        self.make_pdf()
        self.assertEqual(verified_pdf_authors(self.pdf), ['Ada Lovelace','Alan Turing'])

    def test_split_blocks_on_the_same_row_preserve_author_order(self):
        self.make_pdf(continuation=', Grace Hopper')
        self.assertEqual(verified_pdf_authors(self.pdf), ['Ada Lovelace','Alan Turing','Grace Hopper'])

    def test_wrong_author_metadata_is_not_used(self):
        self.make_pdf(hint='An Unrelated Author')
        self.assertEqual(verified_pdf_authors(self.pdf), [])

    def test_visible_byline_can_be_recovered_without_author_tag(self):
        self.make_pdf(hint='')
        self.assertEqual(verified_pdf_authors(self.pdf), ['Ada Lovelace','Alan Turing'])

    def test_full_author_tag_and_oxford_comma_do_not_reject_the_byline(self):
        names = 'Ada Lovelace, Alan Turing, and Grace Hopper'
        self.make_pdf(hint=names, byline=names)
        self.assertEqual(verified_pdf_authors(self.pdf), ['Ada Lovelace', 'Alan Turing', 'Grace Hopper'])

    def test_visible_names_with_alternate_chinese_spellings(self):
        from ingest.metadata import _byline_names
        self.assertEqual(_byline_names('Chao Wang (王超); Yan Lu (卢艳)'), ['Chao Wang', 'Yan Lu'])

    def test_body_prose_is_not_an_author(self):
        self.make_pdf(hint='', byline='Measurements show stable nanobubbles over time.')
        self.assertEqual(verified_pdf_authors(self.pdf), [])

    def test_footnote_before_and_does_not_join_two_names(self):
        self.make_pdf(hint='', byline='Ada Lovelace*and Alan Turing')
        self.assertEqual(verified_pdf_authors(self.pdf), ['Ada Lovelace', 'Alan Turing'])

    def test_title_and_authors_can_share_one_pdf_text_block(self):
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((50, 60), self.title + '\nAda Lovelace, Alan Turing', fontsize=11)
            page.insert_text((50, 110), 'Department of Science, University of Example', fontsize=8)
            document.set_metadata({'title': self.title})
            document.save(self.pdf)
        self.assertEqual(verified_pdf_authors(self.pdf), ['Ada Lovelace', 'Alan Turing'])

    def test_interleaved_affiliations_do_not_save_just_the_first_author(self):
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((50, 60), self.title, fontsize=14)
            page.insert_text((50, 90), 'Ada Lovelace', fontsize=11)
            page.insert_text((50, 110), 'Department of Science, University of Example', fontsize=9)
            page.insert_text((50, 135), 'Alan Turing', fontsize=11)
            page.insert_text((50, 155), 'Department of Engineering, University of Example', fontsize=9)
            page.insert_text((50, 190), 'Abstract: This paper describes experiments.', fontsize=10)
            document.set_metadata({'title': self.title})
            document.save(self.pdf)
        self.assertEqual(verified_pdf_authors(self.pdf), [])

    def test_backfill_updates_citations_without_changing_identity_or_summary(self):
        self.make_pdf()
        path=self.database()
        original=self.pdf.read_bytes()
        self.assertEqual(reconcile_authors(path),1)
        with sqlite3.connect(path) as conn:
            self.assertEqual(conn.execute('SELECT paper_id,authors,summary FROM papers').fetchone(),
                             ('stable-id','Ada Lovelace; Alan Turing','Existing summary'))
            self.assertEqual(conn.execute('SELECT citation_key,authors FROM citation_catalog').fetchone(),
                             ('existing-key','Ada Lovelace; Alan Turing'))
        self.assertEqual(self.pdf.read_bytes(), original)
        self.assertEqual(reconcile_authors(path),0)

    def test_backfill_preserves_existing_curated_author_list(self):
        self.make_pdf()
        path=self.database('A Curated Author')
        self.assertEqual(reconcile_authors(path),0)
        with sqlite3.connect(path) as conn:
            self.assertEqual(conn.execute('SELECT authors FROM papers').fetchone()[0],'A Curated Author')

    def test_new_imports_recover_authors_without_a_reference_library(self):
        self.make_pdf()
        section={'name':self.title,'text':'A brief article excerpt.','page_start':1,'page_end':1}
        with patch.object(parse_pdfs,'_convert',return_value=object()), \
             patch.object(parse_pdfs,'_extract_with_fallback',return_value=(self.title,[section],'')):
            result=parse_pdfs.parse_pdf(self.pdf,{},None)
        self.assertEqual(result['authors'],['Ada Lovelace','Alan Turing'])


if __name__ == '__main__':
    unittest.main()
