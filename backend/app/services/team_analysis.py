"""Snapshot-based AI review storage. Generated advice never changes a plan."""
import hashlib
import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from ..repositories.activities import list_activity_rows_between
from ..repositories.settings import get_setting_value, set_setting_value
from .coaches import build_team_coaching
from .dashboard import build_recent_context
from .strength import get_strength_sessions_between


def analysis_context(conn):
    today = datetime.now(ZoneInfo('Europe/Warsaw')).date()
    start = today - timedelta(days=today.weekday())
    baseline = start - timedelta(weeks=4)
    recent = build_recent_context(conn, recent_activity_limit=30)
    team = build_team_coaching(conn, today=today)
    facts = {'window': team['window'], 'specialists': {
        sport: {key: report[key] for key in ('totals', 'baseline', 'evidence', 'risks', 'limitations')}
        for sport, report in team['specialists'].items()
    }}
    snapshot = {
        'week_start': start.isoformat(), 'through_date': today.isoformat(),
        'team_facts': facts,
        'activities': list_activity_rows_between(conn, baseline.isoformat(), today.isoformat()),
        'strength_detail': get_strength_sessions_between(conn, baseline, today),
        **{key: recent.get(key) for key in (
            'active_plan', 'active_goals', 'athlete_profile', 'athlete_brief',
            'latest_subjective_state', 'recent_feedback', 'recent_notes', 'readiness',
            'training_load', 'modality_restrictions', 'workout_template_settings',
        )},
    }
    # Remove response-generation timestamps so merely refreshing does not stale a review.
    def stable(value):
        if isinstance(value, dict):
            return {key: stable(item) for key, item in value.items() if key not in {'generated_at', 'updated_at', 'fetched_at'}}
        if isinstance(value, list):
            return [stable(item) for item in value]
        return value
    snapshot = stable(snapshot)
    digest = hashlib.sha256(json.dumps(snapshot, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return {'context_key': digest, 'snapshot': snapshot}


def read_saved_analysis(conn, week):
    raw = get_setting_value(conn, f'team_analysis:{week}')
    return json.loads(raw) if raw else None


def get_analysis(conn):
    context = analysis_context(conn)
    week = context['snapshot']['week_start']
    review = read_saved_analysis(conn, week)
    return {'context_key': context['context_key'], 'week_start': week,
            'through_date': context['snapshot']['through_date'], 'review': review,
            'stale': bool(review and review['context_key'] != context['context_key']),
            'evidence': {row['id']: {'name': row.get('name') or row['type'], 'date': row['date'][:10]} for row in context['snapshot']['activities']},
            'facts': context['snapshot']['team_facts']}


def save_analysis(conn, result):
    context = analysis_context(conn)
    if result.context_key != context['context_key']:
        raise HTTPException(409, 'Training changed during the review. Generate a fresh review.')
    if {item.sport for item in result.specialists} != {'running', 'cycling', 'strength'}:
        raise HTTPException(422, 'Exactly one report from each specialist is required.')
    ids = {row['id'] for row in context['snapshot']['activities']}
    if any(set(item.evidence_ids) - ids for item in result.specialists):
        raise HTTPException(422, 'A specialist cited an activity outside this snapshot.')
    payload = {**result.model_dump(), 'generated_at': datetime.now(ZoneInfo('Europe/Warsaw')).isoformat(),
               'week_start': context['snapshot']['week_start'], 'through_date': context['snapshot']['through_date'],
               'generator': 'coaching-team-v2'}
    set_setting_value(conn, f"team_analysis:{payload['week_start']}", json.dumps(payload))
    conn.commit()
    return payload
