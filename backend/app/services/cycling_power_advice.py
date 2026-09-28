"""On-demand advice snapshots; reading this service never invokes an LLM."""
import hashlib
import json
from datetime import datetime, timezone

from fastapi import HTTPException
from ..repositories.settings import get_setting_value, set_setting_value
from .power_trends import get_cycling_power_trends_data, build_cycling_power_coaching_context

ADVICE_KEY = 'cycling_power_advice:v1'


def profile_context(conn):
    profile = get_cycling_power_trends_data(conn)
    # Hash source facts, not moving date windows or response timestamps.
    key = hashlib.sha256(json.dumps(profile, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return key, profile


def advice_context(conn):
    key, profile = profile_context(conn)
    snapshot = build_cycling_power_coaching_context(conn, include_thresholds=False)
    # Full monthly rows are unnecessary for a short priorities review.
    snapshot.pop('monthly_coverage', None)
    snapshot['recording_gaps'] = snapshot['recording_gaps'][-12:]
    return {'context_key': key, 'snapshot': snapshot}


def get_advice(conn):
    key, profile = profile_context(conn)
    raw = get_setting_value(conn, ADVICE_KEY)
    review = json.loads(raw) if raw else None
    return {'context_key': key, 'review': review,
            'stale': bool(review and review['context_key'] != key)}


def save_advice(conn, result):
    # Keep context validation and saving atomic with respect to sync writes.
    conn.execute('BEGIN IMMEDIATE')
    try:
        key, profile = profile_context(conn)
        if result.context_key != key:
            raise HTTPException(409, 'Cycling data changed during the review. Request updated advice.')
        ids = {row['activity_id'] for row in profile['efforts']}
        if not ids:
            raise HTTPException(422, 'Record measured cycling power before requesting advice.')
        if set(result.evidence_ids) - ids:
            raise HTTPException(422, 'Advice cites a ride outside this power profile.')
        payload = {**result.model_dump(), 'generated_at': datetime.now(timezone.utc).isoformat()}
        set_setting_value(conn, ADVICE_KEY, json.dumps(payload))
        conn.commit()
        return payload
    except Exception:
        conn.rollback()
        raise
