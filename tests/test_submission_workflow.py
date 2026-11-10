"""Publication records, repeated review rounds, and preserved journal history."""
import sqlite3
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from jfr.db.schema import DDL, get_conn, init_db
from jfr.tracker import (
    InvalidTransitionError, WorkflowValidationError, add_reviewer_comment,
    create_manuscript, create_submission, get_submission, list_active_submissions,
    list_publications, record_publication, transition_submission,
    update_reviewer_comment, upsert_journal,
)


class WorkflowFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.db = self.root / 'db.sqlite'
        self.conn = init_db(self.db)
        self.addCleanup(self.conn.close)
        upsert_journal(self.conn, {'id': 'journal', 'name': 'Test Journal', 'publisher': 'Test Press'})
        self.ms = create_manuscript(self.conn, 'A test manuscript', 'Abstract', 'Claim')

    def submission(self, state='drafting', manuscript=None):
        return create_submission(self.conn, manuscript or self.ms, 'journal', initial_state=state)

    def advance(self, sub, *states):
        for state in states:
            transition_submission(self.conn, sub, state)

    def comment(self, sub, review_round=1):
        add_reviewer_comment(self.conn, sub, 1, 'Explain the experimental controls.', round=review_round)
        return self.conn.execute('SELECT MAX(id) FROM reviewer_comment').fetchone()[0]


class WorkflowTests(WorkflowFixture):
    def test_complete_publication_with_two_review_rounds(self):
        sub = self.submission()
        self.advance(sub, 'internal_review', 'awaiting_supervisor_approval', 'submitted', 'under_review')
        submitted_at = get_submission(self.conn, sub)['submitted_at']
        first = self.comment(sub)
        self.advance(sub, 'revision_requested_major', 'revising')
        with self.assertRaisesRegex(InvalidTransitionError, 'remaining reviewer'):
            transition_submission(self.conn, sub, 'resubmitted')
        update_reviewer_comment(self.conn, first, response_text='Added control measurements.')
        with self.assertRaises(InvalidTransitionError):
            transition_submission(self.conn, sub, 'resubmitted')
        update_reviewer_comment(self.conn, first, is_addressed=True)
        self.advance(sub, 'resubmitted', 'under_review')
        second = self.comment(sub, 2)
        workflow = get_submission(self.conn, sub)['workflow']
        self.assertEqual((workflow['round'], workflow['pending'], workflow['total']), (2, 1, 1))
        self.advance(sub, 'revision_requested_minor', 'revising')
        update_reviewer_comment(self.conn, second, response_text='Clarified in section 2.', is_addressed=True)
        self.advance(sub, 'resubmitted', 'accepted', 'proofs')
        self.assertIn(sub, [s['id'] for s in list_active_submissions(self.conn)])
        record_publication(self.conn, sub, '2026-10-20', doi='https://doi.org/10.1234/paper', notes='Online publication')
        saved = get_submission(self.conn, sub)
        self.assertEqual(saved['current_state'], 'published')
        self.assertEqual(saved['publication_doi'], '10.1234/paper')
        self.assertEqual(saved['submitted_at'], submitted_at)
        self.assertEqual(saved['workflow']['round'], 2)
        self.assertEqual([e['round'] for e in saved['workflow']['timeline'] if e['to_state'] == 'under_review'], [1, 2])
        self.assertEqual(saved['transitions'][-1]['notes'], 'Online publication')
        self.assertEqual(list_active_submissions(self.conn), [])
        self.assertEqual(list_publications(self.conn)[0]['manuscript_title'], 'A test manuscript')
        with self.assertRaises(InvalidTransitionError):
            transition_submission(self.conn, sub, 'revising')

    def test_publication_requires_acceptance_and_a_reference(self):
        sub = self.submission()
        with self.assertRaises(InvalidTransitionError):
            record_publication(self.conn, sub, '2026-10-20', doi='10.1234/paper')
        with self.assertRaises(InvalidTransitionError):
            transition_submission(self.conn, sub, 'published')
        self.advance(sub, 'internal_review', 'awaiting_supervisor_approval', 'submitted', 'under_review', 'accepted')
        with self.assertRaises(WorkflowValidationError):
            record_publication(self.conn, sub, '2026-10-20')
        with self.assertRaises(InvalidTransitionError):
            transition_submission(self.conn, sub, 'published')
        self.assertEqual(get_submission(self.conn, sub)['current_state'], 'accepted')

    def test_publication_validation_is_atomic(self):
        sub = self.submission('accepted')
        invalid = [
            {'publication_date': 'not a date', 'doi': '10.1234/paper'},
            {'publication_date': '2026-02-30', 'doi': '10.1234/paper'},
            {'publication_date': '2026-10-20', 'doi': 'invalid'},
            {'publication_date': '2026-10-20', 'url': 'javascript:alert(1)'},
            {'publication_date': '2026-10-20', 'url': 'https://user:password@example.com'},
            {'publication_date': '2026-10-20', 'url': 'https://[invalid'},
            {'publication_date': '2026-10-20', 'url': 'https://example.com:invalid'},
        ]
        for values in invalid:
            with self.subTest(values=values), self.assertRaises(WorkflowValidationError):
                record_publication(self.conn, sub, **values)
        saved = get_submission(self.conn, sub)
        self.assertIsNone(saved['publication_date'])
        self.assertEqual(len(saved['transitions']), 1)

    def test_publication_can_skip_proofs_and_update_without_duplicate_event(self):
        sub = self.submission('accepted')
        record_publication(self.conn, sub, '2026-10-20', doi='10.1234/paper')
        record_publication(self.conn, sub, '2026-10-21', doi='10.1234/paper', url='https://example.com/paper')
        saved = get_submission(self.conn, sub)
        self.assertEqual(len(saved['transitions']), 2)
        self.assertEqual(saved['publication_date'], '2026-10-21')
        self.assertEqual(next(s['status'] for s in saved['workflow']['stages'] if s['key'] == 'proofs'), 'unrecorded')

    def test_comment_needs_response_and_belongs_to_submission(self):
        sub = self.submission('under_review')
        comment = self.comment(sub)
        with self.assertRaises(WorkflowValidationError):
            update_reviewer_comment(self.conn, comment, is_addressed=True)
        with self.assertRaises(ValueError):
            update_reviewer_comment(self.conn, comment, sub_id='different', response_text='Changed')
        with self.assertRaises(WorkflowValidationError):
            self.comment(sub, 2)
        update_reviewer_comment(self.conn, comment, response_text='Changed', is_addressed=True)
        with self.assertRaises(WorkflowValidationError):
            update_reviewer_comment(self.conn, comment, response_text='')
        update_reviewer_comment(self.conn, comment, response_text='', is_addressed=False)
        self.assertEqual(get_submission(self.conn, sub)['workflow']['pending'], 1)

    def test_one_active_attempt_and_rejection_preserves_old_history(self):
        sub = self.submission('submitted')
        with self.assertRaises(WorkflowValidationError):
            self.submission()
        transition_submission(self.conn, sub, 'rejected_desk')
        second = self.submission()
        self.assertNotEqual(sub, second)
        self.assertEqual(len(list_active_submissions(self.conn)), 1)
        self.assertEqual(get_submission(self.conn, sub)['current_state'], 'rejected_desk')

    def test_published_manuscript_does_not_start_another_attempt(self):
        sub = self.submission('accepted')
        record_publication(self.conn, sub, '2026-10-20', doi='10.1234/paper')
        with self.assertRaises(WorkflowValidationError):
            self.submission()

    def test_schema_migration_preserves_legacy_records_and_responses(self):
        legacy = self.root / 'legacy.sqlite'
        conn = sqlite3.connect(legacy)
        conn.executescript(DDL)
        conn.execute("INSERT INTO manuscript VALUES ('m','Legacy title','Abstract','flat','Claim','[]','[]',NULL,'2025-01-01','2025-01-01')")
        conn.execute("INSERT INTO journal (id,name,publisher,publisher_family) VALUES ('j','Journal','Press','press')")
        conn.execute("INSERT INTO submission VALUES ('s','m','j','accepted','2025-01-01','2025-01-01','2025-02-01')")
        conn.execute("INSERT INTO reviewer_comment (submission_id,round,reviewer_number,comment_text,response_text,received_at) VALUES ('s',1,1,'Feedback','Existing response','2025-01-01')")
        conn.commit()
        conn.close()
        for _ in range(2):
            init_db(legacy).close()
        conn = get_conn(legacy)
        self.addCleanup(conn.close)
        saved = get_submission(conn, 's')
        self.assertEqual(saved['reviewer_comments'][0]['response_text'], 'Existing response')
        self.assertEqual(saved['reviewer_comments'][0]['is_addressed'], 0)
        record_publication(conn, 's', '2026-10-20', doi='10.1234/legacy')
        self.assertEqual(get_submission(conn, 's')['current_state'], 'published')

    def test_matching_history_keeps_acceptance_after_publication(self):
        from jfr.matching.engine import build_user_history
        sub = self.submission('accepted')
        record_publication(self.conn, sub, '2026-10-20', doi='10.1234/paper')
        self.assertEqual(build_user_history(self.conn, 'another-manuscript', 'journal')['prior_acceptances'], 1)


class WorkflowRouteTests(WorkflowFixture):
    def setUp(self):
        super().setUp()
        from jfr.web import app as web
        from jfr.config import Settings
        self.web = web
        settings = Settings(data_dir=self.root, db_path=self.db, attachments_dir=self.root / 'attachments')
        patcher = patch.object(web, '_settings', settings)
        patcher.start()
        self.addCleanup(patcher.stop)
        # No lifespan: route tests use an isolated database and do not load models.
        self.client = TestClient(web.app, client=('127.0.0.1', 12345))
        self.addCleanup(self.client.close)

    @staticmethod
    def pdf():
        import pymupdf
        with pymupdf.open() as document:
            document.new_page().insert_text((72, 72), 'Final published paper')
            return document.tobytes()

    def test_pdf_publication_upload_read_and_metadata_edit(self):
        sub = self.submission('accepted')
        response = self.client.post(f'/submissions/{sub}/publication', data={'publication_date': '2026-10-20'},
                                    files={'pdf': ('final.pdf', self.pdf(), 'application/pdf')}, follow_redirects=False)
        self.assertEqual(response.status_code, 303, response.text)
        final = self.client.get(f'/submissions/{sub}/published.pdf')
        self.assertEqual(final.status_code, 200)
        self.assertTrue(final.content.startswith(b'%PDF-'))
        self.assertIn('inline', final.headers['content-disposition'])
        edit = self.client.post(f'/api/submissions/{sub}/publication', json={'publication_date': '2026-10-21'})
        self.assertEqual(edit.status_code, 200, edit.text)
        self.assertEqual(edit.json()['publication_pdf_name'], 'final.pdf')
        archive = self.client.get('/publications')
        self.assertEqual(archive.status_code, 200)
        self.assertIn('A test manuscript', archive.text)
        self.assertIn('Read final PDF', archive.text)
        self.assertEqual(len(self.client.get('/api/publications').json()), 1)

    def test_failed_upload_does_not_change_state_or_leave_files(self):
        sub = self.submission('accepted')
        for content, date in [(b'not a PDF', '2026-10-20'), (b'%PDF-invalid', '2026-10-20'), (self.pdf(), 'invalid')]:
            with self.subTest(date=date, size=len(content)):
                response = self.client.post(f'/submissions/{sub}/publication', data={'publication_date': date},
                                            files={'pdf': ('final.pdf', content, 'application/pdf')})
                self.assertEqual(response.status_code, 422, response.text)
        self.assertEqual(list((self.root / 'attachments').rglob('*.pdf')), [])
        self.assertEqual(get_submission(self.conn, sub)['current_state'], 'accepted')

    def test_workflow_pages_and_pending_comment_gate(self):
        sub = self.submission('under_review')
        self.comment(sub)
        self.advance(sub, 'revision_requested_minor', 'revising')
        detail = self.client.get(f'/submissions/{sub}')
        self.assertEqual(detail.status_code, 200, detail.text)
        self.assertIn('data-stage="revision" data-status="current"', detail.text)
        self.assertIn('Another review round', detail.text)
        self.assertIn('Round 1', detail.text)
        self.assertIn('disabled title="Address the remaining comments first"', detail.text)
        denied = self.client.post(f'/api/submissions/{sub}/transition', json={'to_state': 'resubmitted'})
        self.assertEqual(denied.status_code, 422)
        for route in ['/submissions', f'/submissions?ms={self.ms}', '/publications']:
            response = self.client.get(route)
            self.assertEqual(response.status_code, 200, response.text)

    def test_response_form_unlocks_resubmission_and_proofs_offer_publication(self):
        sub = self.submission('under_review')
        comment = self.comment(sub)
        self.advance(sub, 'revision_requested_minor', 'revising')
        saved = self.client.post(f'/submissions/{sub}/comments/{comment}/edit', data={
            'review_round': 1, 'reviewer_number': 1, 'comment_text': 'Explain the experimental controls.',
            'response_text': 'Added the controls in Figure 2.', 'is_addressed': 'true',
        }, follow_redirects=False)
        self.assertEqual(saved.status_code, 303, saved.text)
        self.assertEqual(get_submission(self.conn, sub)['workflow']['pending'], 0)
        for state in ['resubmitted', 'accepted', 'proofs']:
            response = self.client.post(f'/submissions/{sub}/transition', data={'to_state': state}, follow_redirects=False)
            self.assertEqual(response.status_code, 303, response.text)
        detail = self.client.get(f'/submissions/{sub}')
        self.assertEqual(detail.status_code, 200)
        self.assertIn('Record publication</a>', detail.text)
        overview = self.client.get('/submissions')
        self.assertIn('already have an active timeline', overview.text)

    def test_routes_reject_early_publication_invalid_metadata_and_cross_submission_edit(self):
        sub = self.submission('under_review')
        comment = self.comment(sub)
        early = self.client.post(f'/submissions/{sub}/publication', data={'publication_date': '2026-10-20', 'doi': '10.1234/paper'})
        self.assertEqual(early.status_code, 422)
        self.advance(sub, 'accepted')
        invalid = self.client.post(f'/api/submissions/{sub}/publication', json={'publication_date': '2026-10-20', 'url': 'https://[invalid'})
        self.assertEqual(invalid.status_code, 422)
        cross = self.client.post(f'/submissions/different/comments/{comment}/edit', data={'comment_text': 'Changed', 'response_text': 'Response'})
        self.assertEqual(cross.status_code, 404)
        self.assertEqual(get_submission(self.conn, sub)['reviewer_comments'][0]['comment_text'], 'Explain the experimental controls.')


if __name__ == '__main__':
    unittest.main()
