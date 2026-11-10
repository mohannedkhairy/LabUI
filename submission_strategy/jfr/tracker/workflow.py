"""Present the real publication path, including repeated reviewer rounds."""
from datetime import date

STATE_LABELS = {
    'drafting': 'Drafting', 'internal_review': 'Internal review',
    'awaiting_supervisor_approval': 'Supervisor approval', 'submitted': 'Submitted',
    'under_review': 'Peer review', 'revision_requested_minor': 'Minor revisions requested',
    'revision_requested_major': 'Major revisions requested', 'revising': 'Revising',
    'resubmitted': 'Revision submitted', 'accepted': 'Accepted', 'proofs': 'Proofs & production',
    'published': 'Published', 'rejected_desk': 'Desk rejection',
    'rejected_post_review': 'Rejected after review', 'withdrawn': 'Withdrawn',
}
STAGES = [
    ('draft', 'Draft', ['drafting']),
    ('internal', 'Internal review', ['internal_review']),
    ('supervisor', 'Supervisor approval', ['awaiting_supervisor_approval']),
    ('submitted', 'Submitted', ['submitted']),
    ('review', 'Peer review', ['under_review', 'resubmitted']),
    ('revision', 'Revisions', ['revision_requested_minor', 'revision_requested_major', 'revising']),
    ('accepted', 'Accepted', ['accepted']),
    ('proofs', 'Proofs', ['proofs']),
    ('published', 'Published', ['published']),
]
ACTION_LABELS = {
    'internal_review': 'Send for internal review', 'drafting': 'Return to drafting',
    'awaiting_supervisor_approval': 'Request supervisor approval', 'submitted': 'Record journal submission',
    'under_review': 'Record peer review started', 'revision_requested_minor': 'Minor revisions requested',
    'revision_requested_major': 'Major revisions requested', 'revising': 'Start revisions',
    'resubmitted': 'Record revision submitted', 'accepted': 'Record acceptance',
    'proofs': 'Start proofs & production', 'published': 'Record publication',
    'rejected_desk': 'Record desk rejection', 'rejected_post_review': 'Record rejection',
    'withdrawn': 'Withdraw this attempt',
}
HINTS = {
    'drafting': 'Finish the manuscript, figures, and supporting material before internal review.',
    'internal_review': 'Work through internal feedback, then request supervisor approval. Return to drafting if needed.',
    'awaiting_supervisor_approval': 'Once approval is received and journal formatting is complete, record the submission.',
    'submitted': 'Wait for the journal to start peer review or record its editorial decision.',
    'under_review': 'Record the editor’s decision: minor revisions, major revisions, acceptance, or rejection.',
    'revision_requested_minor': 'Add this round’s reviewer comments, then start revising the manuscript.',
    'revision_requested_major': 'Add this round’s reviewer comments, then start revising the manuscript.',
    'revising': 'Make each requested change, write its response, and mark it addressed before resubmitting.',
    'resubmitted': 'Your revision is with the journal. Another peer-review cycle starts a new round.',
    'accepted': 'Record any proof or production work, then save the published paper when it is available.',
    'proofs': 'Check the proofs and publication details. Record the published paper when it is available.',
    'published': 'The published paper and its full review history are saved here.',
    'rejected_desk': 'This journal attempt has ended. Keep its history and start a new attempt at another journal.',
    'rejected_post_review': 'This journal attempt has ended. Use the feedback when preparing the next attempt.',
    'withdrawn': 'This attempt was withdrawn. Its history remains available.',
}


def review_round(submission):
    reviewed = sum(t['to_state'] == 'under_review' for t in submission.get('transitions', []))
    recorded = max((c['round'] for c in submission.get('reviewer_comments', [])), default=0)
    return max(1, reviewed, recorded)


def build_workflow(submission):
    state = submission['current_state']
    transitions = submission.get('transitions', [])
    visited = {t['to_state'] for t in transitions}
    visited.add(state)
    current_index = next((i for i, (_, _, states) in enumerate(STAGES) if state in states), None)
    stages = []
    for i, (key, label, states) in enumerate(STAGES):
        recorded = bool(visited.intersection(states))
        status = 'current' if i == current_index else 'complete' if recorded else 'unrecorded' if current_index is not None and i < current_index else 'future'
        stages.append({'key': key, 'label': label, 'status': status, 'x': 58 + i * 112,
                       'lines': label.split(' ', 1), 'recorded': recorded,
                       'date': next((t['occurred_on'] for t in reversed(transitions) if t['to_state'] in states and t.get('occurred_on')), None)})
    number = review_round(submission)
    comments = submission.get('reviewer_comments', [])
    rounds = []
    for round_number in sorted({c['round'] for c in comments}, reverse=True):
        items = [c for c in comments if c['round'] == round_number]
        addressed = sum(bool(c.get('is_addressed')) and bool((c.get('response_text') or '').strip()) for c in items)
        rounds.append({'number': round_number, 'comments': items, 'total': len(items), 'addressed': addressed})
    current = next((r for r in rounds if r['number'] == number), {'total': 0, 'addressed': 0})
    timeline, cycle = [], 0
    for transition in transitions:
        to_state = transition['to_state']
        if to_state == 'under_review':
            cycle += 1
        timeline.append({**transition, 'label': STATE_LABELS.get(to_state, to_state),
                         'round': max(1, cycle) if to_state in {'under_review','revision_requested_minor','revision_requested_major','revising','resubmitted'} else None})
    days = 0
    if transitions:
        try:
            entered = date.fromisoformat(transitions[-1].get('occurred_on') or transitions[-1]['transitioned_at'][:10])
            days = max(0, (date.today() - entered).days)
        except ValueError:
            pass
    pending = current['total'] - current['addressed']
    return {'label': STATE_LABELS.get(state, state), 'hint': HINTS.get(state, ''),
            'stages': stages, 'timeline': timeline, 'round': number, 'rounds': rounds,
            'total': current['total'], 'addressed': current['addressed'], 'pending': pending,
            'response_percent': round(100 * current['addressed'] / current['total']) if current['total'] else 0,
            'days_in_stage': days, 'can_resubmit': pending == 0,
            'stage_date_known': bool(transitions and transitions[-1].get('occurred_on')),
            'started_on': transitions[0].get('occurred_on') if transitions else None,
            'can_publish': state in {'accepted','proofs','published'},
            'closed': state in {'published','rejected_desk','rejected_post_review','withdrawn'}}
