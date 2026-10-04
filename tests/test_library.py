"""Library organization must preserve PDFs and survive database reconnects.

Run: PYTHONPATH=submission_strategy submission_strategy/.venv/bin/python -m unittest discover -s tests
"""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch
from fastapi import HTTPException
from jfr.db.schema import init_db
from jfr.web import library_routes as library


class LibraryTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        db = Path(self.temp.name) / 'jfr.db'
        init_db(db).close()
        def connect():
            conn = sqlite3.connect(db)
            conn.row_factory = sqlite3.Row
            conn.execute('PRAGMA foreign_keys=ON')
            return conn
        self.papers = [{'paper_id': f'paper-{i}', 'title': f'Paper {i:02d}', 'authors': 'Researcher', 'year': 2025, 'source_pdf': '/library/source.pdf'} for i in range(35)]
        for name, value in [('_conn', connect), ('_papers', lambda: [dict(p) for p in self.papers])]:
            mock = patch.object(library, name, value)
            mock.start()
            self.addCleanup(mock.stop)

    def listing(self, **kwargs):
        return library.library_list(page=kwargs.pop('page', 1), page_size=kwargs.pop('page_size', 30), **kwargs)

    def test_pagination_search_and_empty_library(self):
        self.assertEqual(len(self.listing(page=2)['papers']), 5)
        self.assertEqual(self.listing(q='paper 34')['total'], 1)
        self.papers.clear()
        self.assertEqual(self.listing()['total'], 0)

    def test_folder_membership_persists_and_deletion_preserves_papers(self):
        folder = library.create_folder(library.FolderIn(name='Reading'))
        library.assign_folder(library.MembershipIn(paper_ids=['paper-0', 'paper-1'], folder_id=folder['id']))
        self.assertEqual(self.listing(folder=folder['id'])['total'], 2)
        self.assertEqual(self.listing()['unfiled'], 33)
        library.delete_folder(folder['id'])
        self.assertEqual(self.listing()['total_all'], 35)
        self.assertEqual(self.listing()['unfiled'], 35)

    def test_invalid_assignment_does_not_partially_move_papers(self):
        folder = library.create_folder(library.FolderIn(name='Reading'))
        with self.assertRaises(HTTPException):
            library.assign_folder(library.MembershipIn(paper_ids=['paper-0', 'missing'], folder_id=folder['id']))
        self.assertEqual(self.listing(folder=folder['id'])['total'], 0)

    def test_duplicate_folder_and_unfiling(self):
        folder = library.create_folder(library.FolderIn(name='Reading'))
        with self.assertRaises(HTTPException):
            library.create_folder(library.FolderIn(name='reading'))
        library.assign_folder(library.MembershipIn(paper_ids=['paper-0'], folder_id=folder['id']))
        library.assign_folder(library.MembershipIn(paper_ids=['paper-0']))
        self.assertEqual(self.listing(folder=folder['id'])['total'], 0)


if __name__ == '__main__':
    unittest.main()
