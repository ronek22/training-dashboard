import json
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from fastapi import HTTPException

from .life_load import get_life_load_days, missed_on_tagged_days


def list_reviews(conn):
    return [dict(row) for row in conn.execute(
        "SELECT * FROM weekly_reviews WHERE generator = 'codex-cli' ORDER BY week_start DESC"
    ).fetchall()]


def review_status(conn, now=None):
    local = (now or datetime.now(ZoneInfo('Europe/Warsaw'))).astimezone(ZoneInfo('Europe/Warsaw'))
    monday = local.date() - timedelta(days=local.weekday())
    if local.weekday() != 6 or (local.hour, local.minute) < (23, 59):
        monday -= timedelta(days=7)
    due = monday.isoformat()
    reviews = list_reviews(conn)
    return {'due_week': due, 'missing': not any(row['week_start'] == due for row in reviews),
            'latest_available_week': reviews[0]['week_start'] if reviews else None}


MONTH_FIRST_REVIEW_LAST_DAY = 7


def is_monthly_goal_review_week(week):
    """The first weekly review of a month is the week whose Sunday falls on days 1-7."""
    return (week + timedelta(days=6)).day <= MONTH_FIRST_REVIEW_LAST_DAY


def monthly_goal_review(conn, week, today=None):
    """Read-only goals digest for the month's first weekly review; applies nothing."""
    if not is_monthly_goal_review_week(week):
        return None
    from .goal_review import build_goal_review
    from .goal_suggestions import build_goal_suggestions
    review = build_goal_review(conn, today=today)
    suggestions = build_goal_suggestions(conn, today=today)
    portfolio = review['portfolio']
    return {
        'month': (week + timedelta(days=6)).strftime('%Y-%m'),
        'attention_count': review['attention_count'],
        'decisions': [
            {'goal_id': item['goal_id'], 'title': item['title'], 'verdict': item['review']['verdict'],
             'label': item['review']['label'], 'headline': item['review']['headline']}
            for item in review['goals'] if item['review']['needs_attention']
        ],
        'portfolio': {key: portfolio[key] for key in ('status', 'summary', 'ratio', 'implied_weekly_hours', 'actual_weekly_hours')},
        'suggestions_count': len(suggestions['suggestions']),
        'link': '/goals',
    }


def review_context(conn, week):
    from .coaches import build_team_coaching
    from .team_analysis import read_saved_analysis
    start = week.isoformat()
    end = (week + timedelta(days=7)).isoformat()
    baseline = (week - timedelta(days=28)).isoformat()

    def rows(query, params):
        return [dict(row) for row in conn.execute(query, params).fetchall()]

    plans = rows('SELECT * FROM weekly_plans WHERE week_start >= ? AND week_start < ? ORDER BY week_start', (baseline, end))
    for plan in plans:
        plan['days'] = json.loads(plan.pop('days_json'))
    return {
        'team_coaching': build_team_coaching(conn, week_start=week),
        'saved_team_analysis': read_saved_analysis(conn, week.isoformat()),
        'goal_review': monthly_goal_review(conn, week),
        'life_load': {
            'days': list(get_life_load_days(conn, start, (week + timedelta(days=6)).isoformat()).values()),
            **missed_on_tagged_days(conn, week),
        },
        'review_week': start,
        'week_end': (week + timedelta(days=6)).isoformat(),
        'timezone': 'Europe/Warsaw',
        'activities': rows('SELECT * FROM activities WHERE date >= ? AND date < ? ORDER BY date', (baseline, end)),
        'plans': plans,
        'feedback': rows('''SELECT f.*, a.date FROM activity_feedback f
            JOIN activities a ON a.id = f.activity_id WHERE a.date >= ? AND a.date < ?''', (baseline, end)),
        'coaching_notes': rows('SELECT * FROM coach_notes WHERE date >= ? AND date < ? ORDER BY date', (baseline, end)),
        'prior_reviews': rows("SELECT * FROM weekly_reviews WHERE generator = 'codex-cli' AND week_start >= ? AND week_start < ? ORDER BY week_start DESC", (baseline, start)),
        # The app's evidence-based wins for the week, so "improved" starts from what really went well.
        'week_wins': _week_wins_for_review(conn, week),
        'previous_change': next((r['proposed_change'] for r in list_reviews(conn)
                                 if r['week_start'] == (week - timedelta(days=7)).isoformat()), None),
    }


def _week_wins_for_review(conn, week):
    from .week_wins import build_week_wins
    try:
        return build_week_wins(conn, week, today=week + timedelta(days=7))['wins']
    except Exception:  # The review must still run if a win cannot be computed.
        return []


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
