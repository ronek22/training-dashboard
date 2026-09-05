import json
from datetime import timedelta

from fastapi import HTTPException


def list_reviews(conn):
    return [dict(row) for row in conn.execute(
        "SELECT * FROM weekly_reviews WHERE generator = 'codex-cli' ORDER BY week_start DESC"
    ).fetchall()]


def review_context(conn, week):
    start = week.isoformat()
    end = (week + timedelta(days=7)).isoformat()
    baseline = (week - timedelta(days=28)).isoformat()

    def rows(query, params):
        return [dict(row) for row in conn.execute(query, params).fetchall()]

    plans = rows('SELECT * FROM weekly_plans WHERE week_start >= ? AND week_start < ? ORDER BY week_start', (baseline, end))
    for plan in plans:
        plan['days'] = json.loads(plan.pop('days_json'))
    return {
        'review_week': start,
        'week_end': (week + timedelta(days=6)).isoformat(),
        'timezone': 'Europe/Warsaw',
        'activities': rows('SELECT * FROM activities WHERE date >= ? AND date < ? ORDER BY date', (baseline, end)),
        'plans': plans,
        'feedback': rows('''SELECT f.*, a.date FROM activity_feedback f
            JOIN activities a ON a.id = f.activity_id WHERE a.date >= ? AND a.date < ?''', (baseline, end)),
        'coaching_notes': rows('SELECT * FROM coach_notes WHERE date >= ? AND date < ? ORDER BY date', (baseline, end)),
        'prior_reviews': rows("SELECT * FROM weekly_reviews WHERE generator = 'codex-cli' AND week_start >= ? AND week_start < ? ORDER BY week_start DESC", (baseline, start)),
        'previous_change': next((r['proposed_change'] for r in list_reviews(conn)
                                 if r['week_start'] == (week - timedelta(days=7)).isoformat()), None),
    }


def save_review(conn, review):
    week = review.week_start.isoformat()
    # Immutable once generated: a retried job must not rewrite coaching history.
    existing = conn.execute("SELECT * FROM weekly_reviews WHERE week_start = ? AND generator = 'codex-cli'", (week,)).fetchone()
    if existing:
        return dict(existing)
    previous_week = (review.week_start - timedelta(days=7)).isoformat()
    previous = conn.execute(
        "SELECT proposed_change FROM weekly_reviews WHERE week_start = ? AND generator = 'codex-cli'", (previous_week,)
    ).fetchone()
    previous_change = previous['proposed_change'] if previous else None
    if not previous_change and review.previous_change_outcome != 'not_assessed':
        raise HTTPException(422, 'No previous-week suggestion to assess')
    with conn:
        conn.execute('''
            INSERT INTO weekly_reviews
                (week_start, improved, missed, proposed_change, previous_change,
                 previous_change_outcome, generator, outcome_reason)
            VALUES (?, ?, ?, ?, ?, ?, 'codex-cli', ?)
            ON CONFLICT(week_start) DO UPDATE SET
                improved=excluded.improved, missed=excluded.missed,
                proposed_change=excluded.proposed_change,
                previous_change=excluded.previous_change,
                previous_change_outcome=excluded.previous_change_outcome,
                generator=excluded.generator, outcome_reason=excluded.outcome_reason,
                updated_at=CURRENT_TIMESTAMP
            WHERE weekly_reviews.generator != 'codex-cli'
        ''', (week, review.improved, review.missed, review.proposed_change,
              previous_change, review.previous_change_outcome, review.outcome_reason))
    return dict(conn.execute('SELECT * FROM weekly_reviews WHERE week_start = ?', (week,)).fetchone())
