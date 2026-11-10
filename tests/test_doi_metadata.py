"""DOI enrichment must prove it belongs to this PDF, rather than a cited paper."""
import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'Local_Rag/rag'))
from ingest.doi_metadata import validate_doi_record


class DoiMetadataTests(unittest.TestCase):
    def setUp(self):
        self.record = {'DOI': '10.1234/example', 'title': ['Nanobubbles and the hydrophobic attraction'],
                       'author': [{'given': 'Ada', 'family': 'Lovelace'}, {'given': 'Alan', 'family': 'Turing'}]}
        self.headers = {'1': 'Journal\nNanobubbles and the hydrophobic attraction\nAda Lovelace, Alan Turing\nUniversity\nAbstract'}

    def test_full_names_are_accepted_only_with_matching_title_and_order(self):
        result = validate_doi_record(self.record, self.headers)
        self.assertEqual(result['authors'], ['Ada Lovelace', 'Alan Turing'])
        self.assertEqual(result['doi'], '10.1234/example')

    def test_another_papers_doi_or_a_reference_list_cannot_supply_metadata(self):
        for header in ['A different article by Ada Lovelace and Alan Turing',
                       'Nanobubbles and the hydrophobic attraction\nAlan Turing, Ada Lovelace',
                       'x' * 2300 + self.headers['1']]:
            with self.subTest(header=header[:60]), self.assertRaises(ValueError):
                validate_doi_record(self.record, {'1': header})

    def test_incomplete_registry_author_list_is_not_used(self):
        with self.assertRaisesRegex(ValueError, 'incomplete'):
            validate_doi_record(dict(self.record, author=[{'family': 'Lovelace'}]), self.headers)

    def test_ligatures_and_publisher_html_do_not_break_exact_title_verification(self):
        record = {'title': ['Nanobubble &amp; water dif<b>fusion</b>'], 'author': [{'given': 'André', 'family': 'Müller'}]}
        result = validate_doi_record(record, {'1': 'Nanobubble & water diﬀusion\nAndre Muller\nUniversity'})
        self.assertEqual(result['authors'], ['André Müller'])


if __name__ == '__main__':
    unittest.main()
