"""Historical event dates must not change the recorded workflow or audit clock."""
from datetime import date
from pathlib import Path
import sqlite3
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from jfr.db.schema import DDL, init_db
from jfr.tracker import (
    create_manuscript, create_submission, get_submission, record_publication,
    transition_submission, update_timeline_dates, upsert_journal, WorkflowValidationError,
)


class DateFixture(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.db = self.root / 'db.sqlite'
        self.conn = init_db(self.db)
        self.addCleanup(self.conn.close)
        upsert_journal(self.conn, {'id': 'j', 'name': 'Test Journal', 'publisher': 'Test Press'})
        self.ms = create_manuscript(self.conn, 'Historical manuscript', 'Abstract', 'Claim')

    def create(self, state='submitted', occurred_on=None):
        return create_submission(self.conn, self.ms, 'j', initial_state=state, occurred_on=occurred_on)

    def get(self, sub):
        return get_submission(self.conn, sub)


class SubmissionDateTests(DateFixture):
    def test_historical_stages_have_independent_dates_and_real_ages(self):
        sub = self.create(occurred_on='2023-01-02')
        transition_submission(self.conn, sub, 'under_review', occurred_on='2023-01-09')
        saved = self.get(sub)
        self.assertEqual(saved['submitted_at'][:10], '2023-01-02')
        self.assertEqual([t['occurred_on'] for t in saved['transitions']], ['2023-01-02', '2023-01-09'])
        self.assertEqual(saved['workflow']['days_in_stage'], (date.today() - date(2023, 1, 9)).days)
        self.assertTrue(saved['workflow']['stage_date_known'])
        self.assertEqual(next(s['date'] for s in saved['workflow']['stages'] if s['key'] == 'review'), '2023-01-09')
        self.assertNotEqual(saved['created_at'][:10], '2023-01-02')

    def test_bulk_edit_completed_history_preserves_ids_notes_audit_times_and_state(self):
        sub = self.create()
        transition_submission(self.conn, sub, 'under_review', notes='Sent to reviewers')
        transition_submission(self.conn, sub, 'accepted', notes='Editor accepted the paper')
        record_publication(self.conn, sub, '2024-05-01', doi='10.1234/paper')
        before = self.get(sub)
        days = ['2024-01-01', '2024-01-12', '2024-03-20', '2024-04-15']
        update_timeline_dates(self.conn, sub, {event['id']: day for event, day in zip(before['transitions'], days)})
        saved = self.get(sub)
        self.assertEqual(saved['current_state'], 'published')
        self.assertEqual(saved['submitted_at'][:10], days[0])
        self.assertEqual(saved['publication_date'], days[-1])
        self.assertEqual(saved['created_at'], before['created_at'])
        for original, edited in zip(before['transitions'], saved['transitions']):
            for key in ['id', 'from_state', 'to_state', 'notes', 'transitioned_at']:
                self.assertEqual(original[key], edited[key], key)
        self.assertEqual([e['occurred_on'] for e in saved['workflow']['timeline']], days)

    def test_bad_dates_and_reverse_order_are_rejected_atomically(self):
        sub = self.create(occurred_on='2024-01-01')
        transition_submission(self.conn, sub, 'under_review', occurred_on='2024-02-01')
        before = self.get(sub)
        first, last = [t['id'] for t in before['transitions']]
        for dates in [{first: '2024-03-01'}, {first: '2024-01-02', last: 'invalid'}, {last: '2024-02-30'}, {last: '20240202'}]:
            with self.subTest(dates=dates), self.assertRaises(WorkflowValidationError):
                update_timeline_dates(self.conn, sub, dates)
            self.assertEqual(self.get(sub), before)
        with self.assertRaises(WorkflowValidationError):
            transition_submission(self.conn, sub, 'accepted', occurred_on='2024-01-15')
        self.assertEqual(self.get(sub), before)

    def test_unknown_old_dates_do_not_prevent_backdating_known_events(self):
        sub = self.create()
        transition_submission(self.conn, sub, 'under_review')
        events = self.get(sub)['transitions']
        update_timeline_dates(self.conn, sub, {events[1]['id']: '2022-06-01'})
        self.assertIsNone(self.get(sub)['transitions'][0]['occurred_on'])
        update_timeline_dates(self.conn, sub, {events[0]['id']: '2022-05-01'})
        self.assertEqual(self.get(sub)['submitted_at'][:10], '2022-05-01')

    def test_same_day_review_cycles_keep_their_sequence_and_rounds(self):
        sub = self.create(occurred_on='2024-01-01')
        states = ['under_review', 'revision_requested_minor', 'revising', 'resubmitted', 'under_review']
        for state in states:
            transition_submission(self.conn, sub, state, occurred_on='2024-01-01')
        before = self.get(sub)
        update_timeline_dates(self.conn, sub, {e['id']: '2023-06-01' for e in before['transitions']})
        saved = self.get(sub)
        self.assertEqual([e['to_state'] for e in saved['transitions']], ['submitted', *states])
        self.assertEqual(saved['workflow']['round'], 2)
        self.assertEqual([e['round'] for e in saved['workflow']['timeline'] if e['to_state'] == 'under_review'], [1, 2])

    def test_other_submission_events_cannot_be_edited(self):
        sub = self.create()
        ms2 = create_manuscript(self.conn, 'Another manuscript', 'Abstract', 'Claim')
        other = create_submission(self.conn, ms2, 'j')
        foreign = self.get(other)['transitions'][0]['id']
        first = self.get(sub)['transitions'][0]['id']
        before = self.get(sub)
        with self.assertRaises(ValueError):
            update_timeline_dates(self.conn, sub, {first: '2021-01-01', foreign: '2021-02-01'})
        self.assertEqual(self.get(sub), before)

    def test_publication_form_date_and_timeline_date_stay_synchronized(self):
        sub = self.create('accepted', '2024-01-01')
        record_publication(self.conn, sub, '2024-02-01', doi='10.1234/paper')
        record_publication(self.conn, sub, '2024-02-15', doi='10.1234/paper')
        saved = self.get(sub)
        self.assertEqual(saved['transitions'][-1]['occurred_on'], '2024-02-15')
        self.assertEqual(len(saved['transitions']), 2)
        with self.assertRaises(WorkflowValidationError):
            record_publication(self.conn, sub, '2023-12-01', doi='10.1234/changed')
        self.assertEqual(self.get(sub), saved)
        with self.assertRaises(WorkflowValidationError):
            update_timeline_dates(self.conn, sub, {saved['transitions'][-1]['id']: None})
        self.assertEqual(self.get(sub), saved)

    def test_journal_turnaround_uses_event_dates(self):
        from jfr.matching.engine import _median_turnaround
        sub = self.create(occurred_on='2024-01-01')
        transition_submission(self.conn, sub, 'under_review', occurred_on='2024-01-02')
        transition_submission(self.conn, sub, 'accepted', occurred_on='2024-01-11')
        self.assertEqual(_median_turnaround(self.conn, 'j'), 10)

    def test_additive_migration_distinguishes_known_dates_from_legacy_log_times(self):
        path = self.root / 'legacy.sqlite'
        with sqlite3.connect(path) as conn:
            conn.executescript(DDL)
            conn.execute('ALTER TABLE submission ADD COLUMN publication_date TEXT')
            conn.execute("INSERT INTO manuscript VALUES ('m','Title','Abstract','flat','Claim','[]','[]',NULL,'2025-01-01','2025-01-01')")
            conn.execute("INSERT INTO journal (id,name,publisher,publisher_family) VALUES ('j','Journal','Press','press')")
            conn.execute("INSERT INTO submission VALUES ('s','m','j','published','2024-01-01','2025-01-01','2025-01-01','2024-04-01')")
            conn.execute("INSERT INTO submission_transition (submission_id,to_state,transitioned_at) VALUES ('s','accepted','2025-01-01T12:00:00+00:00')")
            conn.execute("INSERT INTO submission_transition (submission_id,to_state,transitioned_at) VALUES ('s','published','2025-01-01T13:00:00+00:00')")
        conn = init_db(path)
        self.addCleanup(conn.close)
        saved = get_submission(conn, 's')
        self.assertIsNone(saved['transitions'][0]['occurred_on'])
        self.assertEqual(saved['transitions'][1]['occurred_on'], '2024-04-01')
        update_timeline_dates(conn, 's', {saved['transitions'][0]['id']: '2024-03-01'})
        init_db(path).close()
        self.assertEqual(get_submission(conn, 's')['transitions'][0]['occurred_on'], '2024-03-01')
        self.assertEqual(get_submission(conn, 's')['transitions'][0]['transitioned_at'], '2025-01-01T12:00:00+00:00')


class SubmissionDateRouteTests(DateFixture):
    def setUp(self):
        super().setUp()
        from jfr.web import app as web
        from jfr.config import Settings
        patcher = patch.object(web, '_settings', Settings(data_dir=self.root, db_path=self.db, attachments_dir=self.root / 'attachments'))
        patcher.start()
        self.addCleanup(patcher.stop)
        self.client = TestClient(web.app, client=('127.0.0.1', 12345))
        self.addCleanup(self.client.close)

    def test_historical_create_and_publication_work_through_api(self):
        response = self.client.post('/api/submissions', json={'manuscript_id': self.ms, 'journal_id': 'j', 'initial_state': 'accepted', 'occurred_on': '2020-01-01'})
        self.assertEqual(response.status_code, 201, response.text)
        sub = response.json()['id']
        response = self.client.post(f'/api/submissions/{sub}/publication', json={'publication_date': '2020-02-01', 'doi': '10.1234/paper'})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual([e['occurred_on'] for e in response.json()['transitions']], ['2020-01-01', '2020-02-01'])
        page = self.client.get(f'/submissions/{sub}')
        self.assertIn('2020-01-01', page.text)
        self.assertIn('Edit timeline dates', page.text)
        self.assertEqual(len(response.json()['transitions']), 2)

    def test_timeline_api_updates_and_rejects_duplicate_or_unowned_events(self):
        sub = self.create()
        event = self.get(sub)['transitions'][0]['id']
        payload = {'transition_id': event, 'occurred_on': '2022-01-01'}
        response = self.client.patch(f'/api/submissions/{sub}/timeline', json={'dates': [payload]})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()['submitted_at'][:10], '2022-01-01')
        duplicate = self.client.patch(f'/api/submissions/{sub}/timeline', json={'dates': [payload, payload]})
        self.assertEqual(duplicate.status_code, 422)
        unknown = self.client.patch(f'/api/submissions/{sub}/timeline', json={'dates': [{'transition_id': event + 999, 'occurred_on': '2021-01-01'}]})
        self.assertEqual(unknown.status_code, 404)

    def test_html_bulk_edit_preserves_inputs_on_error_and_saves_historical_dates(self):
        sub = self.create()
        transition_submission(self.conn, sub, 'under_review')
        first, second = self.get(sub)['transitions']
        fields = {f"event_date_{first['id']}": '2022-02-01', f"event_date_{second['id']}": '2022-01-01'}
        failed = self.client.post(f'/submissions/{sub}/timeline/dates', data=fields)
        self.assertEqual(failed.status_code, 422, failed.text)
        self.assertIn('must be on or after', failed.text)
        self.assertIn('value="2022-02-01"', failed.text)
        self.assertIsNone(self.get(sub)['transitions'][0]['occurred_on'])
        fields[f"event_date_{first['id']}"] = '2021-12-01'
        saved = self.client.post(f'/submissions/{sub}/timeline/dates', data=fields, follow_redirects=False)
        self.assertEqual(saved.status_code, 303)
        self.assertTrue(saved.headers['location'].endswith('#timeline'))
        self.assertEqual(self.get(sub)['submitted_at'][:10], '2021-12-01')

    def test_new_status_form_preserves_invalid_date_and_decision_notes(self):
        sub = self.create(occurred_on='2024-01-01')
        failed = self.client.post(f'/submissions/{sub}/transition', data={'to_state': 'under_review', 'occurred_on': '2023-01-01', 'notes': 'Historical review started'})
        self.assertEqual(failed.status_code, 422)
        self.assertIn('value="2023-01-01"', failed.text)
        self.assertIn('Historical review started</textarea>', failed.text)
        self.assertEqual(self.get(sub)['current_state'], 'submitted')
        response = self.client.post(f'/submissions/{sub}/transition', data={'to_state': 'under_review', 'occurred_on': '2024-01-11'}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        self.assertEqual(self.get(sub)['transitions'][-1]['occurred_on'], '2024-01-11')

    def test_starting_stage_and_date_are_available_in_creation_form(self):
        page = self.client.get('/submissions')
        self.assertEqual(page.status_code, 200)
        self.assertIn('name="initial_state"', page.text)
        self.assertIn('name="occurred_on"', page.text)
        response = self.client.post('/submissions/create', data={'manuscript_id': self.ms, 'journal_id': 'j', 'initial_state': 'submitted', 'occurred_on': '2021-06-01'}, follow_redirects=False)
        self.assertEqual(response.status_code, 303)
        sub = response.headers['location'].split('/')[-1]
        self.assertEqual(self.get(sub)['submitted_at'][:10], '2021-06-01')
        self.assertIn('History starts 2021-06-01', self.client.get(response.headers['location']).text)


if __name__ == '__main__':
    unittest.main()
