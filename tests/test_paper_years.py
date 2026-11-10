"""Publication years must be supported by this paper, and survive future indexing."""
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
from paper_years import record_year, text_year, matching_record, apply_year
from ingest import parse_pdfs, build_index
import citations


class PublicationYearTests(unittest.TestCase):
    def test_final_issue_year_wins_over_early_online_and_registration_dates(self):
        record = {'published-print': {'date-parts': [[2025, 1]]},
                  'published-online': {'date-parts': [[2024, 8, 22]]},
                  'issued': {'date-parts': [[2024, 8, 22]]},
                  'created': {'date-parts': [[2023]]}}
        self.assertEqual(record_year(record)['year'], 2025)
        self.assertIsNone(record_year({'created': {'date-parts': [[2020]]}, 'deposited': {'date-parts': [[2026]]}}))

    def test_citation_year_beats_received_online_and_copyright_dates(self):
        text = ('Received 19 June 2024; Accepted 19 August 2024\n'
                'Journal of Colloid and Interface Science 678 (2025) 322–333\n'
                'Available online 22 August 2024\n© 2024 Elsevier Inc.')
        self.assertEqual(text_year(text)['year'], 2025)
        self.assertEqual(text_year('Cite This: Langmuir 2020, 36, 15618–15621')['year'], 2020)
        self.assertEqual(text_year('J. Chem. Phys. 156, 044505 (2022)')['year'], 2022)

    def test_download_date_title_year_and_references_do_not_supply_publication_year(self):
        text = ('Madrid-2019 force field\nDownloaded 25 October 2026\nReceived 14 July 2021\n'
                'References\nJournal of Chemistry 12 (1999) 12–16')
        self.assertIsNone(text_year(text))
        self.assertIsNone(text_year('PDF created in 2026. An experiment on a 2019 force field.'))

    def test_conflicting_citation_years_are_left_for_review(self):
        self.assertIsNone(text_year('Journal of Physics 10 (2020) 22–25\nJournal of Physics 11 (2021) 33–37'))

    def test_doi_suffixes_online_dates_and_body_references_are_not_issue_years(self):
        self.assertEqual(text_year('J. Fluid Mech. (2021), vol. 913, A45, doi:10.1017/jfm.2020.1167')['year'], 2021)
        self.assertIsNone(text_year('VOL. 7, NO. 1, 49–59\nMOLECULAR PHARMACEUTICS\nPublished on Web 12/03/2009', strong_only=True))
        self.assertEqual(text_year('Molecular Simulation, 2017\nVOL. 43, NO. 1, 1–12\nhttp://dx.doi.org/10.1080/08927022.2016.1221071')['year'], 2017)
        self.assertIsNone(text_year('water purification technologies (Burns et al.\n1997, Nakano et al. 2005, Yamasaki et al. 2009, 2010).'))

    def test_arxiv_identifier_is_not_a_publication_year(self):
        self.assertEqual(text_year('arXiv:1809.12345v2 [physics.chem-ph] 10 Sep 2018')['year'], 2018)
        self.assertIsNone(text_year('arXiv:1809.12345'))

    def test_related_doi_cannot_supply_year_of_a_different_title(self):
        record = {'DOI': '10.1234/paper', 'title': ['A study of nanobubble stability'],
                  'author': [{'family': 'Lovelace'}]}
        self.assertTrue(matching_record(record, record['title'][0], 'Ada Lovelace'))
        self.assertFalse(matching_record(record, 'A different scientific study', 'Ada Lovelace', ['10.1234/paper']))
        self.assertFalse(matching_record(record, record['title'][0], 'A Different Author'))

    def test_year_backfill_preserves_curated_values_and_citation_keys(self):
        with sqlite3.connect(':memory:') as conn:
            conn.executescript("""CREATE TABLE papers(paper_id TEXT PRIMARY KEY,year INTEGER,summary TEXT);
                CREATE TABLE citation_catalog(paper_id TEXT,citation_key TEXT,year INTEGER);
                INSERT INTO papers VALUES('new',NULL,'Preserved summary'),('curated',1998,'Other summary');
                INSERT INTO citation_catalog VALUES('new','stable-key',NULL),('curated','old-key',1998);""")
            evidence = {'year': 2025, 'source': 'pdf:journal-citation', 'quote': 'Journal 678 (2025) 322–333'}
            self.assertTrue(apply_year(conn, 'new', evidence))
            self.assertFalse(apply_year(conn, 'curated', evidence))
            self.assertEqual(conn.execute("SELECT year,summary FROM papers WHERE paper_id='new'").fetchone(), (2025, 'Preserved summary'))
            self.assertEqual(conn.execute("SELECT citation_key,year FROM citation_catalog WHERE paper_id='new'").fetchone(), ('stable-key', 2025))
            self.assertEqual(conn.execute("SELECT year FROM papers WHERE paper_id='curated'").fetchone()[0], 1998)

    def test_reindex_preserves_existing_year_and_fills_a_missing_year(self):
        with sqlite3.connect(':memory:') as conn:
            conn.executescript(build_index.DDL)
            paper = {'paper_id': 'p', 'title': 'A scientific paper', 'year': 2025}
            build_index._insert_paper(conn, paper)
            build_index._insert_paper(conn, dict(paper, year=2024))
            self.assertEqual(conn.execute('SELECT year FROM papers').fetchone()[0], 2025)
            build_index._insert_paper(conn, dict(paper, paper_id='missing', year=None))
            build_index._insert_paper(conn, dict(paper, paper_id='missing', year=2026))
            self.assertEqual(conn.execute("SELECT year FROM papers WHERE paper_id='missing'").fetchone()[0], 2026)

    def test_new_pdf_import_recovers_printed_year_without_reference_library(self):
        import pymupdf
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / 'paper.pdf'
            title = 'A scientific study of nanobubble stability'
            with pymupdf.open() as document:
                page = document.new_page()
                page.insert_text((40, 50), 'Journal of Science 42 (2025) 100–110')
                page.insert_text((40, 90), title)
                document.set_metadata({'title': title})
                document.save(path)
            sections = [{'name': 'Body', 'text': 'Scientific source text.', 'page_start': 1, 'page_end': 1}]
            with patch.object(parse_pdfs, '_convert', return_value=object()), \
                 patch.object(parse_pdfs, '_extract_with_fallback', return_value=(title, sections, '')):
                result = parse_pdfs.parse_pdf(path, {}, None)
            self.assertEqual(result['year'], 2025)

    def test_citation_sync_detects_a_year_change_when_title_is_unchanged(self):
        with tempfile.TemporaryDirectory() as temporary, patch.object(citations, 'DB_PATH', Path(temporary) / 'rag.db'):
            with sqlite3.connect(citations.DB_PATH) as conn:
                conn.executescript(build_index.DDL)
                build_index._insert_paper(conn, {'paper_id': 'p', 'title': 'Nanobubble stability', 'authors': ['Ada Lovelace']})
                conn.commit()
            citations.init_db()
            citations.sync_rag_papers()
            with sqlite3.connect(citations.DB_PATH) as conn:
                key = conn.execute('SELECT citation_key FROM citation_catalog').fetchone()[0]
                conn.execute("UPDATE papers SET year=2025 WHERE paper_id='p'")
            citations.sync_rag_papers()
            with sqlite3.connect(citations.DB_PATH) as conn:
                new_key, year, aliases = conn.execute('SELECT citation_key,year,aliases_json FROM citation_catalog').fetchone()
                self.assertEqual((new_key, year), ('lovelace2025', 2025))
                self.assertIn(key, json.loads(aliases))


if __name__ == '__main__':
    unittest.main()
