"""Nested uploads must be parsed, and failed PDFs must not report success."""
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "Local_Rag" / "rag"))
from ingest import parse_pdfs


class PdfIngestionTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        root = Path(temporary.name)
        self.papers = root/"papers"
        self.parsed = root/"parsed"
        (self.papers/"nested").mkdir(parents=True)
        self.pdf = self.papers/"nested"/"Paper.PDF"
        self.pdf.write_bytes(b"%PDF-1.7\nTest placeholder; conversion is mocked.")
        for name, value in [("PAPERS_PDF_DIR", self.papers), ("PARSED_DIR", self.parsed),
                            ("PAPERS_LIBRARY", root/"absent.json"), ("MENDELEY_LIBRARY", root/"absent.bib")]:
            mock = patch.object(parse_pdfs, name, value)
            mock.start()
            self.addCleanup(mock.stop)

    def test_nested_uppercase_pdf_is_parsed(self):
        result = {"paper_id": "Paper", "sections": [{"name": "Body", "text": "Readable text"}]}
        with patch.object(parse_pdfs, "DocumentConverter"), patch.object(parse_pdfs, "parse_pdf", return_value=result) as parse:
            parse_pdfs.run()
        self.assertEqual(parse.call_args.args[0], self.pdf)
        self.assertTrue((self.parsed/"Paper.json").exists())

    def test_conversion_failure_is_reported_as_failure(self):
        with patch.object(parse_pdfs, "DocumentConverter"), patch.object(parse_pdfs, "parse_pdf", return_value=None):
            with self.assertRaisesRegex(RuntimeError, "Could not parse 1 PDF"):
                parse_pdfs.run()
        self.assertFalse((self.parsed/"Paper.json").exists())

    def test_title_metadata_is_used_when_docling_labels_title_as_a_section(self):
        import pymupdf
        title = 'A real paper title about nanobubble stability'
        with pymupdf.open() as document:
            page = document.new_page()
            page.insert_text((50, 60), title)
            document.set_metadata({'title': title})
            document.save(self.pdf)
        sections = [{'name': title, 'text': 'A researcher and their affiliation.', 'page_start': 1, 'page_end': 1}]
        with patch.object(parse_pdfs, '_convert', return_value=object()), \
             patch.object(parse_pdfs, '_extract_with_fallback', return_value=(None, sections, '')):
            result = parse_pdfs.parse_pdf(self.pdf, {}, None)
        self.assertEqual(result['title'], title)
        self.assertEqual(result['paper_id'], 'Paper')


if __name__ == "__main__":
    unittest.main()
