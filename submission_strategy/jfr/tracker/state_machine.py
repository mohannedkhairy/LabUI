"""Submission tracker: state machine and CRUD operations."""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from datetime import date
from typing import Optional
import re
from urllib.parse import urlsplit

from jfr.db.schema import VALID_TRANSITIONS, TERMINAL_STATES


class InvalidTransitionError(ValueError):
    pass


class WorkflowValidationError(ValueError):
    pass


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _gen_id(prefix: str) -> str:
    short = uuid.uuid4().hex[:8]
    return f"{prefix}_{short}"


def _event_date(value):
    if value is None or value == '':
        return None
    try:
        if not re.fullmatch(r'\d{4}-\d{2}-\d{2}', value):
            raise ValueError
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise WorkflowValidationError('Enter a valid event date in YYYY-MM-DD format.') from None


def _validate_event_dates(events):
    from .workflow import STATE_LABELS
    previous = None
    for event in events:
        if not event.get('occurred_on'):
            continue
        if previous and event['occurred_on'] < previous['occurred_on']:
            raise WorkflowValidationError(
                f"{STATE_LABELS.get(event['to_state'], event['to_state'])} ({event['occurred_on']}) "
                f"must be on or after {STATE_LABELS.get(previous['to_state'], previous['to_state'])} "
                f"({previous['occurred_on']}). Edit the timeline dates together to correct older records."
            )
        previous = event


def _sync_submission_dates(conn, sub_id):
    submitted = conn.execute("SELECT occurred_on,transitioned_at FROM submission_transition WHERE submission_id=? AND to_state='submitted' ORDER BY id LIMIT 1", (sub_id,)).fetchone()
    if submitted:
        value = submitted['occurred_on'] + 'T00:00:00+00:00' if submitted['occurred_on'] else submitted['transitioned_at']
        conn.execute('UPDATE submission SET submitted_at=? WHERE id=?', (value, sub_id))
    published = conn.execute("SELECT occurred_on FROM submission_transition WHERE submission_id=? AND to_state='published' ORDER BY id DESC LIMIT 1", (sub_id,)).fetchone()
    if published and published['occurred_on']:
        conn.execute('UPDATE submission SET publication_date=? WHERE id=?', (published['occurred_on'], sub_id))


def update_timeline_dates(conn, sub_id, dates):
    """Edit actual event dates atomically; keep the state sequence and log times."""
    with conn:
        if not conn.in_transaction:
            conn.execute('BEGIN IMMEDIATE')
        _update_timeline_dates(conn, sub_id, dates)


def _update_timeline_dates(conn, sub_id, dates):
    if not conn.execute('SELECT 1 FROM submission WHERE id=?', (sub_id,)).fetchone():
        raise ValueError('Submission not found')
    events = [dict(row) for row in conn.execute('SELECT * FROM submission_transition WHERE submission_id=? ORDER BY id', (sub_id,))]
    if not set(dates) <= {event['id'] for event in events}:
        raise ValueError('Timeline event not found in this submission')
    for event in events:
        if event['id'] in dates:
            event['occurred_on'] = _event_date(dates[event['id']])
            if event['to_state'] == 'published' and not event['occurred_on']:
                raise WorkflowValidationError('A published paper needs its publication date. Enter the correct date instead of clearing it.')
    _validate_event_dates(events)
    for event in events:
        if event['id'] in dates:
            conn.execute('UPDATE submission_transition SET occurred_on=? WHERE id=? AND submission_id=?',
                         (event['occurred_on'], event['id'], sub_id))
    _sync_submission_dates(conn, sub_id)
    conn.execute('UPDATE submission SET updated_at=? WHERE id=?', (_now(), sub_id))


# ── Manuscript ─────────────────────────────────────────────────────────────────

def create_manuscript(
    conn: sqlite3.Connection,
    title: str,
    abstract: str,
    principal_claim: str,
    techniques: list[str] = None,
    figures: list[str] = None,
    abstract_format: str = "flat",
    bibtex_key: Optional[str] = None,
    ms_id: Optional[str] = None,
) -> str:
    ms_id = ms_id or _gen_id("ms")
    now = _now()
    conn.execute(
        """INSERT INTO manuscript
           (id, title, abstract, abstract_format, principal_claim,
            techniques_json, figures_json, bibtex_key, created_at, updated_at)
           VALUES (?,?,?,?,?,?,?,?,?,?)""",
        (
            ms_id, title, abstract, abstract_format, principal_claim,
            json.dumps(techniques or []),
            json.dumps(figures or []),
            bibtex_key, now, now,
        ),
    )
    conn.commit()
    return ms_id


def get_manuscript(conn: sqlite3.Connection, ms_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM manuscript WHERE id=?", (ms_id,)).fetchone()
    if not row:
        return None
    return dict(row)


def list_manuscripts(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute("SELECT * FROM manuscript ORDER BY created_at DESC").fetchall()
    return [dict(r) for r in rows]


# ── Journal ────────────────────────────────────────────────────────────────────

def upsert_journal(conn: sqlite3.Connection, journal: dict) -> None:
    conn.execute(
        """INSERT OR REPLACE INTO journal
           (id, name, publisher, publisher_family, issn_print, issn_electronic,
            is_fully_oa, is_hybrid_oa, impact_factor, society_affiliation,
            submission_url, abstract_format, scope_statement, metadata_json)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (
            journal["id"], journal["name"], journal["publisher"],
            journal.get("publisher_family", journal["publisher"].lower().split()[0]),
            journal.get("issn_print"), journal.get("issn_electronic"),
            int(journal.get("is_fully_oa", False)),
            int(journal.get("is_hybrid_oa", False)),
            journal.get("impact_factor"),
            journal.get("society_affiliation"),
            journal.get("submission_url"),
            journal.get("abstract_format"),
            journal.get("scope_statement"),
            json.dumps(journal.get("metadata", {})),
        ),
    )
    conn.commit()


def load_journals_from_yaml(conn: sqlite3.Connection, yaml_path) -> int:
    import yaml
    with open(yaml_path) as f:
        data = yaml.safe_load(f)
    count = 0
    for j in data.get("journals", []):
        upsert_journal(conn, j)
        count += 1
    return count


# ── Submission ─────────────────────────────────────────────────────────────────

def create_submission(
    conn: sqlite3.Connection,
    manuscript_id: str,
    journal_id: str,
    initial_state: str = "drafting",
    sub_id: Optional[str] = None,
    occurred_on: Optional[str] = None,
) -> str:
    with conn:
        if not conn.in_transaction:
            conn.execute('BEGIN IMMEDIATE')
        return _create_submission(conn, manuscript_id, journal_id, initial_state, sub_id, occurred_on)


def _create_submission(conn, manuscript_id, journal_id, initial_state, sub_id, occurred_on):
    occurred_on = _event_date(occurred_on)
    sub_id = sub_id or _gen_id("sub")
    if initial_state not in VALID_TRANSITIONS or initial_state == 'published':
        raise WorkflowValidationError('Start at a valid workflow stage; publication needs its own record.')
    if not conn.execute('SELECT 1 FROM manuscript WHERE id=?', (manuscript_id,)).fetchone():
        raise ValueError('Manuscript not found')
    if not conn.execute('SELECT 1 FROM journal WHERE id=?', (journal_id,)).fetchone():
        raise ValueError('Journal not found')
    existing = conn.execute('SELECT current_state FROM submission WHERE manuscript_id=?', (manuscript_id,)).fetchall()
    if any(row['current_state'] == 'published' for row in existing):
        raise WorkflowValidationError('This manuscript is already published. Create a new manuscript for a new project.')
    if any(row['current_state'] not in TERMINAL_STATES for row in existing):
        raise WorkflowValidationError('This manuscript already has an active submission. Open its timeline or close that attempt first.')
    now = _now()
    conn.execute(
        """INSERT INTO submission
           (id, manuscript_id, journal_id, current_state, created_at, updated_at)
           VALUES (?,?,?,?,?,?)""",
        (sub_id, manuscript_id, journal_id, initial_state, now, now),
    )
    conn.execute(
        """INSERT INTO submission_transition
           (submission_id, from_state, to_state, transitioned_at, occurred_on)
           VALUES (?,?,?,?,?)""",
        (sub_id, None, initial_state, now, occurred_on),
    )
    _sync_submission_dates(conn, sub_id)
    return sub_id


def transition_submission(
    conn: sqlite3.Connection,
    sub_id: str,
    to_state: str,
    notes: Optional[str] = None,
    occurred_on: Optional[str] = None,
) -> None:
    with conn:
        if not conn.in_transaction:
            conn.execute('BEGIN IMMEDIATE')
        _transition_submission(conn, sub_id, to_state, notes, occurred_on)


def _transition_submission(conn, sub_id, to_state, notes=None, occurred_on=None):
    row = conn.execute("SELECT * FROM submission WHERE id=?", (sub_id,)).fetchone()
    if not row:
        raise ValueError(f"Submission {sub_id!r} not found")
    from_state = row["current_state"]
    if from_state in TERMINAL_STATES:
        raise InvalidTransitionError(f"Cannot transition from terminal state {from_state!r}")
    allowed = VALID_TRANSITIONS.get(from_state, [])
    if to_state not in allowed:
        raise InvalidTransitionError(
            f"Invalid transition {from_state!r} → {to_state!r}. "
            f"Allowed: {allowed}"
        )
    if to_state == 'resubmitted':
        workflow = get_submission(conn, sub_id)['workflow']
        if workflow['pending']:
            raise InvalidTransitionError(f"Address all {workflow['pending']} remaining reviewer comment(s) in round {workflow['round']} before resubmitting.")
    if to_state == 'published' and not (
        row['publication_date'] and (row['publication_doi'] or row['publication_url'] or row['publication_pdf'])
    ):
        raise InvalidTransitionError('Use Record publication to add the publication date and a DOI, link, or final PDF.')
    occurred_on = _event_date(row['publication_date'] if to_state == 'published' else occurred_on)
    events = [dict(event) for event in conn.execute('SELECT to_state,occurred_on FROM submission_transition WHERE submission_id=? ORDER BY id', (sub_id,))]
    _validate_event_dates([*events, {'to_state': to_state, 'occurred_on': occurred_on}])
    now = _now()
    changed = conn.execute(
        'UPDATE submission SET current_state=?, updated_at=? WHERE id=? AND current_state=?',
        (to_state, now, sub_id, from_state),
    ).rowcount
    if not changed:
        raise InvalidTransitionError('This submission changed in another window. Refresh its timeline and try again.')
    conn.execute(
        """INSERT INTO submission_transition
           (submission_id, from_state, to_state, transitioned_at, notes, occurred_on)
           VALUES (?,?,?,?,?,?)""",
        (sub_id, from_state, to_state, now, notes, occurred_on),
    )
    _sync_submission_dates(conn, sub_id)


def record_publication(conn, sub_id, publication_date, doi='', url='', pdf=None, pdf_name=None, notes=None):
    sub = conn.execute('SELECT * FROM submission WHERE id=?', (sub_id,)).fetchone()
    if not sub:
        raise ValueError('Submission not found')
    if sub['current_state'] not in {'accepted', 'proofs', 'published'}:
        raise InvalidTransitionError('Record the journal acceptance before adding the published paper.')
    try:
        published = date.fromisoformat(publication_date).isoformat()
    except (TypeError, ValueError):
        raise WorkflowValidationError('Enter a valid publication date.')
    doi = re.sub(r'^https?://(?:dx\.)?doi\.org/', '', (doi or '').strip(), flags=re.I)
    if doi and (len(doi) > 512 or not re.fullmatch(r'10\.\d{4,9}/\S+', doi)):
        raise WorkflowValidationError('Enter a DOI such as 10.1234/example, or leave it blank.')
    url = (url or '').strip()
    if url:
        try:
            parsed = urlsplit(url)
            valid = parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username and not parsed.password
            valid = valid and parsed.port != 0
        except ValueError:
            valid = False
        if len(url) > 2048 or not valid or any(c.isspace() or ord(c) < 32 for c in url):
            raise WorkflowValidationError('The publication link must be an http:// or https:// address without embedded credentials.')
    pdf = pdf if pdf is not None else sub['publication_pdf']
    pdf_name = pdf_name if pdf_name is not None else sub['publication_pdf_name']
    if not (doi or url or pdf):
        raise WorkflowValidationError('Add a DOI, publication link, or final PDF so the published paper can be found.')
    with conn:
        conn.execute('''UPDATE submission SET publication_date=?,publication_doi=?,publication_url=?,
                     publication_pdf=?,publication_pdf_name=?,updated_at=? WHERE id=?''',
                     (published,doi,url,pdf,pdf_name,_now(),sub_id))
        if sub['current_state'] != 'published':
            _transition_submission(conn, sub_id, 'published', notes)
        else:
            event = conn.execute("SELECT id FROM submission_transition WHERE submission_id=? AND to_state='published' ORDER BY id DESC LIMIT 1", (sub_id,)).fetchone()
            if event:
                _update_timeline_dates(conn, sub_id, {event['id']: published})


def get_submission(conn: sqlite3.Connection, sub_id: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM submission WHERE id=?", (sub_id,)).fetchone()
    if not row:
        return None
    sub = dict(row)
    sub["transitions"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM submission_transition WHERE submission_id=? ORDER BY id",
            (sub_id,),
        ).fetchall()
    ]
    sub["reviewer_comments"] = [
        dict(r) for r in conn.execute(
            "SELECT * FROM reviewer_comment WHERE submission_id=? ORDER BY round, reviewer_number,id",
            (sub_id,),
        ).fetchall()
    ]
    from .workflow import build_workflow
    sub['workflow'] = build_workflow(sub)
    return sub


def list_active_submissions(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """SELECT s.*, m.title as manuscript_title, j.name as journal_name
           FROM submission s
           JOIN manuscript m ON m.id = s.manuscript_id
           JOIN journal j ON j.id = s.journal_id
           WHERE s.current_state NOT IN ('published','rejected_desk','rejected_post_review','withdrawn')
           ORDER BY s.updated_at ASC""",
    ).fetchall()
    return [dict(r) for r in rows]


def list_publications(conn):
    return [dict(row) for row in conn.execute('''SELECT s.*,m.title AS manuscript_title,j.name AS journal_name
        FROM submission s JOIN manuscript m ON m.id=s.manuscript_id JOIN journal j ON j.id=s.journal_id
        WHERE s.current_state='published' ORDER BY s.publication_date DESC,s.updated_at DESC''')]


def list_submissions_for_manuscript(conn: sqlite3.Connection, manuscript_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT s.*, j.name as journal_name
           FROM submission s JOIN journal j ON j.id=s.journal_id
           WHERE s.manuscript_id=? ORDER BY s.created_at""",
        (manuscript_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def list_submissions_for_journal(conn: sqlite3.Connection, journal_id: str) -> list[dict]:
    rows = conn.execute(
        """SELECT s.*, m.title as manuscript_title
           FROM submission s JOIN manuscript m ON m.id=s.manuscript_id
           WHERE s.journal_id=? ORDER BY s.created_at""",
        (journal_id,),
    ).fetchall()
    return [dict(r) for r in rows]


def update_reviewer_comment(
    conn: sqlite3.Connection,
    comment_id: int,
    review_round: Optional[int] = None,
    reviewer_number: Optional[int] = None,
    comment_text: Optional[str] = None,
    response_text: Optional[str] = None,
    received_at: Optional[str] = None,
    is_addressed: Optional[bool] = None,
    sub_id: Optional[str] = None,
) -> None:
    original = conn.execute('SELECT * FROM reviewer_comment WHERE id=?', (comment_id,)).fetchone()
    if not original or (sub_id is not None and original['submission_id'] != sub_id):
        raise ValueError('Reviewer comment not found in this submission')
    submission = get_submission(conn, original['submission_id'])
    if review_round is not None and not 1 <= review_round <= submission['workflow']['round']:
        raise WorkflowValidationError('Choose an existing review round.')
    if reviewer_number is not None and reviewer_number < 1:
        raise WorkflowValidationError('Reviewer number must be at least 1.')
    if comment_text is not None and not comment_text.strip():
        raise WorkflowValidationError('Reviewer comment cannot be empty.')
    addressed = original['is_addressed'] if is_addressed is None else is_addressed
    response = original['response_text'] if response_text is None else response_text
    if addressed and not (response or '').strip():
        raise WorkflowValidationError('Write a response before marking this comment addressed.')
    fields, params = [], []
    if review_round is not None:
        fields.append("round=?"); params.append(review_round)
    if reviewer_number is not None:
        fields.append("reviewer_number=?"); params.append(reviewer_number)
    if comment_text is not None:
        fields.append("comment_text=?"); params.append(comment_text)
    if response_text is not None:
        fields.append("response_text=?"); params.append(response_text)
    if received_at is not None:
        fields.append("received_at=?"); params.append(received_at)
    if is_addressed is not None:
        fields.append('is_addressed=?'); params.append(int(is_addressed))
    if not fields:
        return
    params.append(comment_id)
    conn.execute(f"UPDATE reviewer_comment SET {', '.join(fields)} WHERE id=?", params)
    conn.commit()


def update_manuscript(
    conn: sqlite3.Connection,
    ms_id: str,
    title: Optional[str] = None,
    abstract: Optional[str] = None,
    principal_claim: Optional[str] = None,
    techniques: Optional[list[str]] = None,
    bibtex_key: Optional[str] = None,
) -> None:
    import json as _json
    fields, params = [], []
    now = _now()
    if title is not None:
        fields.append("title=?"); params.append(title)
    if abstract is not None:
        fields.append("abstract=?"); params.append(abstract)
    if principal_claim is not None:
        fields.append("principal_claim=?"); params.append(principal_claim)
    if techniques is not None:
        fields.append("techniques_json=?"); params.append(_json.dumps(techniques))
    if bibtex_key is not None:
        fields.append("bibtex_key=?"); params.append(bibtex_key)
    fields.append("updated_at=?"); params.append(now)
    params.append(ms_id)
    conn.execute(f"UPDATE manuscript SET {', '.join(fields)} WHERE id=?", params)
    conn.commit()


def add_reviewer_comment(
    conn: sqlite3.Connection,
    sub_id: str,
    reviewer_number: int,
    comment_text: str,
    round: int = 1,
    received_at: Optional[str] = None,
) -> None:
    submission = get_submission(conn, sub_id)
    if not submission:
        raise ValueError('Submission not found')
    if round < 1 or round > submission['workflow']['round'] or reviewer_number < 1 or not comment_text.strip():
        raise WorkflowValidationError('Use an existing review round, a positive reviewer number, and a nonempty comment.')
    conn.execute(
        """INSERT INTO reviewer_comment
           (submission_id, round, reviewer_number, comment_text, received_at)
           VALUES (?,?,?,?,?)""",
        (sub_id, round, reviewer_number, comment_text, received_at or _now()),
    )
    conn.commit()
