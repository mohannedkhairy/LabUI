"""A model must provide actual PDF evidence for bibliographic labels."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
from ingest.header_metadata import validate_header_metadata
from ingest.parse_pdfs import garbage_ratio, is_garbled
from ingest.metadata import _byline_names


class HeaderMetadataTests(unittest.TestCase):
    def setUp(self):
        self.header = {'2': 'Surface enrichment of ions leads to stability of bulk nanobubbles\nAda Lovelace, Alan Turing and Grace Hopper*\nDepartment of Science\nAbstract\nPaper text'}
        self.result = {'page': 2, 'title': 'Surface enrichment of ions leads to stability of bulk nanobubbles',
                       'title_quote': 'Surface enrichment of ions leads to stability of bulk nanobubbles',
                       'authors': ['Ada Lovelace', 'Alan Turing', 'Grace Hopper'],
                       'byline_quote': 'Ada Lovelace, Alan Turing and Grace Hopper*'}

    def test_supported_title_and_complete_byline_are_accepted(self):
        self.assertEqual(validate_header_metadata(self.result, self.header)['authors'], self.result['authors'])

    def test_supported_title_can_be_recovered_without_inventing_authors(self):
        result = validate_header_metadata(dict(self.result, authors=[], byline_quote=''), self.header)
        self.assertEqual(result['title'], self.result['title'])
        self.assertEqual(result['authors'], [])

    def test_affiliations_between_authors_do_not_count_as_missing_names(self):
        quote = 'Ada Lovelace\nDepartment of Science, University of Example\nAlan Turing\nDepartment of Engineering, University of Example'
        header = {'1': self.result['title'] + '\n' + quote}
        result = dict(self.result, page=1, authors=['Ada Lovelace', 'Alan Turing'], byline_quote=quote)
        self.assertEqual(validate_header_metadata(result, header)['authors'], result['authors'])

    def test_ocr_section_title_requires_a_byline_and_title_page_provenance(self):
        from paper_titles import parsed_header
        record = {'sections': [{'name': 'Fundamental Changes in Air Sparging Flow Patterns',
                               'text': 'by Ada Lovelace, Alan Turing, and Grace Hopper\nAbstract', 'page_start': 1}]}
        self.assertEqual(parsed_header(record)['authors'], ['Ada Lovelace', 'Alan Turing', 'Grace Hopper'])
        record['sections'][0]['page_start'] = 9
        self.assertIsNone(parsed_header(record))
        record['sections'][0].update(page_start=1, text='Measurements show that air flows through the sediment.')
        self.assertIsNone(parsed_header(record))

    def test_invented_title_author_page_order_and_partial_byline_are_rejected(self):
        for change in [{'title': 'Invented scientific title'}, {'authors': ['Alan Turing', 'Ada Lovelace', 'Grace Hopper']},
                       {'page': 1}, {'authors': ['Ada Lovelace']}, {'authors': ['Ada Lovelace', 'A Different Author', 'Grace Hopper']}]:
            with self.subTest(change=change), self.assertRaises(ValueError):
                validate_header_metadata(dict(self.result, **change), self.header)

    def test_replacement_characters_trigger_ocr(self):
        text = 'Available online\n' + '\ufffd' * 300
        self.assertGreater(garbage_ratio(text), .9)
        self.assertTrue(is_garbled([{'text': text}]))
        self.assertFalse(is_garbled([{'text': 'Ordinary scientific text with CO2, Na+ and water. ' * 20}]))

    def test_names_ignore_publisher_marks_and_reconstruct_tex_accents(self):
        self.assertEqual(_byline_names('Bram M. Borkent‡, Holger Sch¨onherr†∗, and G´erard Le Ca¨er♭'),
                         ['Bram M. Borkent', 'Holger Schönherr', 'Gérard Le Caër'])
        self.assertEqual(_byline_names('By Jiandi Wan, Alexander Bick, Matthew Sullivan, and Howard A. Stone*'),
                         ['Jiandi Wan', 'Alexander Bick', 'Matthew Sullivan', 'Howard A. Stone'])
        self.assertEqual(_byline_names('Progress Report'), [])


if __name__ == '__main__':
    unittest.main()
