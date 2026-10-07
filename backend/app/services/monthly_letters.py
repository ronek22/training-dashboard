"""A short monthly letter from the coach: three wins, one pattern, one focus.

The letter looks back at one finished calendar month. Wins come only from
evidence and each one cites its numbers and links to them: all-time records set
that month, streak milestones and the month's longest run of active days,
consistency against the three months before, and goals kept. The pattern is one
observation from sleep debt, life load or the "what worked" memory. The focus is
one thing for next month.

Nothing here calls an LLM. A letter is written only when the athlete asks for
it, then saved as a snapshot and never rewritten: later syncs or edits do not
change a letter already written. A month with little data gets a short, honest
letter instead of padded wins.
"""

from __future__ import annotations

import json
import sqlite3
from calendar import monthrange
from datetime import date, datetime, timedelta
from typing import Any, Optional

from .goals import goal_value_for_window
from .guided_sessions import guided_completion_dates
from .health_data import get_sleep_history
from .life_load import get_life_load_days, missed_on_tagged_days
from .personal_records import _iter_ranked, build_personal_records
from .sleep_debt import BASELINE_NIGHTS, CAUTION_HOURS, build_sleep_debt
from .what_worked import build_what_worked

MAX_WINS = 3
OFFER_DAYS = 7  # The letter is offered on the first days of the month.
PRIOR_MONTHS = 3
THIN_SESSIONS = 4  # Fewer training sessions than this (and few active days) is a thin month.
THIN_ACTIVE_DAYS = 6
MIN_SLEEP_NIGHTS = 14
SLEEP_SHORT_HOURS = 1 / 3  # 20 minutes a night under the usual.
SLEEP_DEBT_DAYS = 7  # Days at or over the caution line that make sleep the pattern.
LIFE_LOAD_DAYS = 4
STREAK_WIN_DAYS = 7
WEEKLY_GOAL_WEEKS_KEPT = 3


# ---------------------------------------------------------------------------
# Month helpers
# ---------------------------------------------------------------------------


def _bounds(month: str) -> tuple[date, date]:
    try:
        start = datetime.strptime(month, "%Y-%m").date()
    except ValueError as error:
        raise ValueError("Month must look like YYYY-MM") from error
    return start, start.replace(day=monthrange(start.year, start.month)[1])


def _shift(month_start: date, months: int) -> date:
    index = month_start.year * 12 + month_start.month - 1 + months
    return date(index // 12, index % 12 + 1, 1)


def _label(month_start: date) -> str:
    return month_start.strftime("%B %Y")


def _name(month_start: date) -> str:
    return month_start.strftime("%B")


def _plural(count: float, word: str) -> str:
    return f"{count:g} {word}{'' if count == 1 else 's'}"


def _hours(minutes: float) -> str:
    return f"{minutes / 60:.1f} h" if minutes < 600 else f"{round(minutes / 60)} h"


def _day(value: str) -> str:
    return date.fromisoformat(value[:10]).strftime("%-d %b")


def _activity_link(activity_id: Optional[str], label: str) -> Optional[dict]:
    return {"to": f"/activities/{activity_id}", "label": label} if activity_id else None


# ---------------------------------------------------------------------------
# Facts about the month
# ---------------------------------------------------------------------------


def _totals(conn: sqlite3.Connection, start: date, end: date) -> dict[str, Any]:
    row = conn.execute(
        "SELECT COUNT(*) AS activities, "
        "SUM(CASE WHEN type != 'Walk' THEN 1 ELSE 0 END) AS sessions, "
        "COALESCE(SUM(CASE WHEN type != 'Walk' THEN duration_min ELSE 0 END), 0) AS minutes, "
        "COUNT(DISTINCT substr(date, 1, 10)) AS active_days "
        "FROM activities WHERE substr(date, 1, 10) BETWEEN ? AND ?",
        (start.isoformat(), end.isoformat()),
    ).fetchone()
    return {"sessions": int(row["sessions"] or 0), "minutes": round(float(row["minutes"] or 0)),
            "active_days": int(row["active_days"] or 0), "days": (end - start).days + 1}


def _prior_average(conn: sqlite3.Connection, month_start: date) -> Optional[dict[str, Any]]:
    """Average of the three months before, counting only months with any activity."""
    months = []
    for back in range(1, PRIOR_MONTHS + 1):
        start = _shift(month_start, -back)
        totals = _totals(conn, start, _shift(start, 1) - timedelta(days=1))
        if totals["sessions"] or totals["active_days"]:
            months.append(totals)
    if not months:
        return None
    return {
        "months": len(months),
        **{key: round(sum(item[key] for item in months) / len(months), 1) for key in ("sessions", "minutes", "active_days")},
    }


def _record_wins(records: dict[str, Any], start: str, end: str) -> Optional[dict[str, Any]]:
    """All-time bests set this month: a progression step after the first ever attempt."""
    found = []
    for category, label, ranked in _iter_ranked(records):
        steps = ranked.get("progression") or []
        before = [step for step in steps if step["date"][:10] < start]
        in_month = [step for step in steps if start <= step["date"][:10] <= end]
        # A first ever attempt is not a record beaten, so it needs an earlier best to compare with.
        if not before or not in_month:
            continue
        best, before = in_month[-1], before[-1]
        name = label if label.startswith(("Longest", "Biggest")) else f"{category} {label}"
        found.append({"name": name, "label": label, "display": best["display"], "date": best["date"][:10],
                      "activity_id": best.get("activity_id"), "previous": before["display"], "previous_date": before["date"][:10]})
    if not found:
        return None
    found.sort(key=lambda item: item["date"])
    links = []
    for item in found[:3]:
        link = _activity_link(item["activity_id"], f"{item['label']} · {_day(item['date'])}")
        if link and link["to"] not in {known["to"] for known in links}:
            links.append(link)
    links.append({"to": "/records", "label": "Records wall"})
    if len(found) == 1:
        item = found[0]
        return {"kind": "record", "score": 95, "headline": f"New all-time best: {item['name']}, {item['display']}",
                "detail": f"Set on {_day(item['date'])}, up from {item['previous']} ({_day(item['previous_date'])}).", "links": links}
    listed = "; ".join(f"{item['name']} {item['display']} (was {item['previous']})" for item in found[:3])
    more = f" and {len(found) - 3} more" if len(found) > 3 else ""
    return {"kind": "record", "score": 95, "headline": f"{len(found)} new all-time bests",
            "detail": f"{listed}{more}.", "links": links}


def _active_dates(conn: sqlite3.Connection) -> list[date]:
    keys = {row[0][:10] for row in conn.execute("SELECT DISTINCT date FROM activities")} | guided_completion_dates(conn)
    return sorted(date.fromisoformat(key) for key in keys)


def _streak_win(conn: sqlite3.Connection, records: dict[str, Any], start: date, end: date) -> Optional[dict[str, Any]]:
    link = [{"to": "/records", "label": "Streaks"}]
    milestones = [item for item in (records.get("streaks") or {}).get("milestones", [])
                  if item["reached_on"] and start.isoformat() <= item["reached_on"] <= end.isoformat()]
    if milestones:
        top = milestones[-1]
        return {"kind": "streak", "score": 90, "headline": f"First {top['days']}-day streak",
                "detail": f"Reached on {_day(top['reached_on'])}: {top['days']} days in a row with an activity or a guided session.",
                "links": link}
    # The month's longest run of active days, and the whole streak it belonged to up to the month's end.
    best, best_start, best_streak = 0, None, 0
    run_start = previous = None
    for day in (item for item in _active_dates(conn) if item <= end):
        run_start = run_start if previous and day == previous + timedelta(days=1) else day
        previous = day
        if day < start:
            continue
        length = (day - max(run_start, start)).days + 1
        if length > best:
            best, best_start, best_streak = length, max(run_start, start), (day - run_start).days + 1
    if best < STREAK_WIN_DAYS:
        return None
    best_end = best_start + timedelta(days=best - 1)
    if best == (end - start).days + 1:
        headline = f"Active every day of {_name(start)}"
    else:
        headline = f"{best} days in a row"
    detail = f"Active every day from {_day(best_start.isoformat())} to {_day(best_end.isoformat())}"
    detail += f", a streak of {best_streak} days by then." if best_streak > best else "."
    return {"kind": "streak", "score": 60, "headline": headline, "detail": detail, "links": link}


def _consistency_win(totals: dict[str, Any], prior: Optional[dict[str, Any]], month_start: date) -> Optional[dict[str, Any]]:
    numbers = (f"{_hours(totals['minutes'])} of training over {_plural(totals['sessions'], 'session')}, "
               f"active on {totals['active_days']} of {totals['days']} days")
    links = [{"to": "/calendar", "label": "Calendar"}]
    if prior and prior["minutes"]:
        change = (totals["minutes"] - prior["minutes"]) / prior["minutes"] * 100
        if change >= -5:
            versus = f"{change:+.0f}% on" if abs(change) >= 5 else "in line with"
            return {"kind": "consistency", "score": 75 if change >= 5 else 55,
                    "headline": f"{_hours(totals['minutes'])} of training in {_name(month_start)}",
                    "detail": f"{numbers}; {versus} your average of {_hours(prior['minutes'])} "
                              f"over the {_plural(prior['months'], 'month')} before.", "links": links}
    if totals["active_days"] >= totals["days"] / 2:
        return {"kind": "consistency", "score": 50, "headline": f"Active on {totals['active_days']} of {totals['days']} days",
                "detail": f"{numbers}.", "links": links}
    return None


def _goal_facts(conn: sqlite3.Connection, start: date, end: date) -> list[dict[str, Any]]:
    """Weekly goals over the month's full weeks and monthly goals over the month."""
    try:
        goals = conn.execute(
            "SELECT * FROM goals WHERE is_active = 1 AND COALESCE(lifecycle_status, 'active') = 'active' "
            # Weekly and monthly goals recur, so only a goal that starts after the month is left out.
            "AND period_type IN ('week', 'month') AND start_date <= ? "
            "ORDER BY CASE commitment WHEN 'anchor' THEN 0 ELSE 1 END, id",
            (end.isoformat(),),
        ).fetchall()
    except sqlite3.Error:
        return []
    monday = start + timedelta(days=(7 - start.weekday()) % 7)
    weeks = []
    while monday + timedelta(days=6) <= end:
        weeks.append(monday)
        monday += timedelta(days=7)
    facts = []
    for goal in goals:
        target = float(goal["target_value"] or 0)
        if not target:
            continue
        base = {"goal_id": goal["id"], "title": goal["title"], "target": target, "anchor": goal["commitment"] == "anchor",
                "period": goal["period_type"], "unit": " km" if goal["metric_type"] in ("ride_km", "run_km") else ""}
        try:
            if goal["period_type"] == "month":
                done = float(goal_value_for_window(conn, goal, start_date=start.isoformat(), end_date=end.isoformat()))
                facts.append({**base, "done": done, "met": done >= target})
            elif weeks:
                kept = sum(
                    1 for week in weeks
                    if goal_value_for_window(conn, goal, start_date=week.isoformat(), end_date=(week + timedelta(days=6)).isoformat()) >= target
                )
                facts.append({**base, "weeks": len(weeks), "kept": kept, "met": kept >= min(WEEKLY_GOAL_WEEKS_KEPT, len(weeks))})
        except (sqlite3.Error, KeyError, ValueError, TypeError):
            continue
    return facts


def _number(value: float) -> str:
    return f"{round(value, 1):g}"


def _goal_win(facts: list[dict[str, Any]]) -> Optional[dict[str, Any]]:
    met = [fact for fact in facts if fact["met"]]
    if not met:
        return None
    fact = met[0]
    if fact["period"] == "month":
        detail = f"{_number(fact['done'])}{fact['unit']} against a target of {_number(fact['target'])}{fact['unit']} for the month."
    else:
        detail = f"Kept in {fact['kept']} of {fact['weeks']} full weeks (target {_number(fact['target'])}{fact['unit']} a week)."
    if fact["anchor"]:
        detail += " That's the anchor goal."
    others = len(met) - 1
    if others:
        detail += f" {_plural(others, 'other goal')} kept too."
    return {"kind": "goal", "score": 88 if fact["anchor"] else 78, "headline": f"{fact['title']}: kept",
            "detail": detail, "links": [{"to": "/goals", "label": "Goals"}]}


# ---------------------------------------------------------------------------
# Pattern and focus
# ---------------------------------------------------------------------------


def _sleep_pattern(conn: sqlite3.Connection, start: date, end: date, today: date) -> Optional[dict[str, Any]]:
    history = get_sleep_history(conn, days=(today - start).days + BASELINE_NIGHTS + 7)
    nights = {item["date"]: float(item["value"]) for item in history if item.get("value")}
    in_month = [hours for night, hours in nights.items() if start.isoformat() <= night <= end.isoformat()]
    baseline_start = (start - timedelta(days=BASELINE_NIGHTS)).isoformat()
    before = sorted(hours for night, hours in nights.items() if baseline_start <= night < start.isoformat())
    if len(in_month) < MIN_SLEEP_NIGHTS or len(before) < MIN_SLEEP_NIGHTS:
        return None
    usual = before[len(before) // 2] if len(before) % 2 else (before[len(before) // 2 - 1] + before[len(before) // 2]) / 2
    average = sum(in_month) / len(in_month)
    debt = build_sleep_debt(history, today=end, series_days=(end - start).days + 1)
    debt_days = sum(1 for point in debt["history"] if point["date"] >= start.isoformat() and point["value"] >= CAUTION_HOURS)
    gap = average - usual
    numbers = (f"{average:.1f} h a night over {len(in_month)} nights against your usual {usual:.1f} h"
               f"; 7-night sleep debt was {CAUTION_HOURS:g} h or more on {_plural(debt_days, 'day')}.")
    link = [{"to": "/metrics?view=recovery", "label": "Sleep trend"}]
    if gap <= -SLEEP_SHORT_HOURS or debt_days >= SLEEP_DEBT_DAYS:
        return {"source": "sleep", "tone": "warn", "score": 3, "headline": f"Sleep ran about {round(-gap * 60)} min a night short"
                if gap < 0 else "Sleep debt built up", "detail": numbers, "links": link}
    return {"source": "sleep", "tone": "good", "score": 1,
            "headline": "Sleep held up" if gap < 0.25 else f"Sleep ran about {round(gap * 60)} min a night longer",
            "detail": numbers, "links": link}


def _life_load_pattern(conn: sqlite3.Connection, start: date, end: date) -> Optional[dict[str, Any]]:
    tagged = get_life_load_days(conn, start.isoformat(), end.isoformat())
    monday = start - timedelta(days=start.weekday())
    on_tagged = 0
    while monday <= end:
        week = missed_on_tagged_days(conn, monday, today=end + timedelta(days=1))
        on_tagged += sum(1 for item in week["missed_on_tagged"] if start.isoformat() <= item["date"] <= end.isoformat())
        monday += timedelta(days=7)
    if len(tagged) < LIFE_LOAD_DAYS and on_tagged < 2:
        return None
    counts: dict[str, int] = {}
    for day in tagged.values():
        for label in day["labels"]:
            counts[label] = counts.get(label, 0) + 1
    kinds = ", ".join(f"{label.lower()} ×{count}" for label, count in sorted(counts.items(), key=lambda item: -item[1]))
    detail = f"{_plural(len(tagged), 'tagged day')} ({kinds})."
    if on_tagged:
        detail += f" {_plural(on_tagged, 'missed planned session')} fell on them: that's life, not motivation."
    return {"source": "life_load", "tone": "info", "score": 2 + (on_tagged >= 2),
            "headline": "Life took a share of the month" if on_tagged else "A busy month outside training",
            "detail": detail, "links": [{"to": "/plan", "label": "Plan"}]}


def _what_worked_pattern(conn: sqlite3.Connection, end: date) -> Optional[dict[str, Any]]:
    try:
        data = build_what_worked(conn, today=end)
    except (sqlite3.Error, KeyError, ValueError):
        return None
    if not data["confirmed"]:
        return None
    pattern = data["confirmed"][0]
    return {"source": "what_worked", "tone": "info", "score": 2, "headline": pattern["statement"],
            "detail": pattern["evidence"], "links": [{"to": "/activities", "label": "What worked"}]}


def _pattern(conn: sqlite3.Connection, start: date, end: date, today: date) -> Optional[dict[str, Any]]:
    candidates = []
    for build in (lambda: _sleep_pattern(conn, start, end, today), lambda: _life_load_pattern(conn, start, end),
                  lambda: _what_worked_pattern(conn, end)):
        try:
            found = build()
        except (sqlite3.Error, KeyError, ValueError, TypeError):
            found = None
        if found:
            candidates.append(found)
    return max(candidates, key=lambda item: item["score"]) if candidates else None


def _focus(conn: sqlite3.Connection, facts: list[dict], pattern: Optional[dict], totals: dict, thin: bool,
           start: date, end: date, next_name: str) -> dict[str, Any]:
    goals_link = [{"to": "/goals", "label": "Goals"}]
    missed = sorted((fact for fact in facts if not fact["met"]), key=lambda fact: not fact["anchor"])
    if missed:
        fact = missed[0]
        if fact["period"] == "month":
            detail = (f"{_number(fact['done'])} of {_number(fact['target'])}{fact['unit']} last month. "
                      f"Spread the {_number(fact['target'])} over {next_name}'s weeks so it isn't a last-week rush.")
        else:
            detail = (f"Kept in {fact['kept']} of {fact['weeks']} full weeks. "
                      "Put the sessions in the plan on Monday so the week has room for them.")
        return {"source": "goal", "headline": f"Protect {fact['title']}", "detail": detail, "links": goals_link}
    if thin:
        return {"source": "restart", "headline": "Two sessions a week, every week",
                "detail": f"Rebuild the habit before the volume: book two sessions in each week of {next_name}.",
                "links": [{"to": "/plan", "label": "Plan"}]}
    if pattern and pattern["source"] == "sleep" and pattern["tone"] == "warn":
        return {"source": "sleep", "headline": "Bank sleep before the hard days",
                "detail": "An early night before each hard session is the cheapest training gain on the table.",
                "links": pattern["links"]}
    if pattern and pattern["source"] == "life_load" and pattern["score"] >= 3:
        return {"source": "life_load", "headline": "Tag busy days early",
                "detail": "Tag known busy days a week ahead so the plan moves hard sessions off them.",
                "links": [{"to": "/plan", "label": "Plan"}]}
    review = conn.execute(
        "SELECT week_start, proposed_change FROM weekly_reviews WHERE generator = 'codex-cli' "
        "AND week_start BETWEEN ? AND ? ORDER BY week_start DESC LIMIT 1",
        ((start - timedelta(days=6)).isoformat(), end.isoformat()),
    ).fetchone()
    if review and review["proposed_change"]:
        return {"source": "review", "headline": "Carry the last weekly change", "detail": review["proposed_change"],
                "links": [{"to": f"/weekly-review?week={review['week_start']}", "label": "Weekly review"}]}
    if pattern and pattern["source"] == "what_worked":
        return {"source": "what_worked", "headline": "Use what works", "detail": pattern["headline"], "links": pattern["links"]}
    return {"source": "default", "headline": f"Repeat the rhythm in {next_name}",
            "detail": f"{_plural(totals['sessions'], 'session')} on {totals['active_days']} days worked. "
                      "Keep the pattern before adding anything.", "links": [{"to": "/plan", "label": "Plan"}]}


# ---------------------------------------------------------------------------
# Letter
# ---------------------------------------------------------------------------


def _opening(month_start: date, totals: dict, prior: Optional[dict], thin: bool, wins: list) -> str:
    name = _name(month_start)
    if not totals["active_days"]:
        return f"Nothing was logged in {name}, so there's nothing to celebrate or criticise. This letter stays short."
    base = f"{name}: {_plural(totals['sessions'], 'training session')} and {_hours(totals['minutes'])} on {totals['active_days']} active days."
    if thin:
        return base + " That's not much to read a month from, so this letter stays short and sticks to what's there."
    if prior and prior["minutes"]:
        change = (totals["minutes"] - prior["minutes"]) / prior["minutes"] * 100
        if change <= -20:
            return base + f" A lighter month than the {prior['months']:g} before ({_hours(prior['minutes'])} on average)."
    return base + (" Here's what stood out." if wins else "")


def build_monthly_letter(conn: sqlite3.Connection, month: str, today: Optional[date] = None) -> dict[str, Any]:
    today = today or datetime.now().date()
    start, end = _bounds(month)
    if end >= today:
        raise ValueError("A letter can only be written once the month is over")
    totals = _totals(conn, start, end)
    prior = _prior_average(conn, start)
    thin = totals["sessions"] < THIN_SESSIONS and totals["active_days"] < THIN_ACTIVE_DAYS
    records = build_personal_records(conn, today=end)
    facts = _goal_facts(conn, start, end)

    streak = _streak_win(conn, records, start, end)
    consistency = None if thin else _consistency_win(totals, prior, start)
    if streak and consistency and consistency["score"] <= 50:
        consistency = None  # Active days alone would repeat the streak.
    candidates = [_record_wins(records, start.isoformat(), end.isoformat()), streak, _goal_win(facts), consistency]
    wins = sorted((win for win in candidates if win), key=lambda win: -win["score"])[:MAX_WINS]
    pattern = None if not totals["active_days"] else _pattern(conn, start, end, today)
    next_name = _name(_shift(start, 1))
    focus = _focus(conn, facts, pattern, totals, thin, start, end, next_name)
    strip = lambda item: {key: value for key, value in item.items() if key != "score"} if item else None
    return {
        "month": month,
        "label": _label(start),
        "start_date": start.isoformat(),
        "end_date": end.isoformat(),
        "thin": thin,
        "totals": totals,
        "prior_average": prior,
        "opening": _opening(start, totals, prior, thin, wins),
        "wins": [strip(win) for win in wins],
        "pattern": strip(pattern),
        "focus": focus,
        "signoff": f"See you at the end of {next_name}." if not thin else f"Small steps in {next_name}. They add up.",
    }


# ---------------------------------------------------------------------------
# Saved letters
# ---------------------------------------------------------------------------


def _row(row: sqlite3.Row) -> dict[str, Any]:
    return {"month": row["month"], "created_at": row["created_at"], **json.loads(row["letter_json"])}


def list_letters(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    return [_row(row) for row in conn.execute("SELECT * FROM monthly_letters ORDER BY month DESC").fetchall()]


def letter_status(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    """The previous month's letter is offered (never written) on the first days of a month."""
    today = today or datetime.now().date()
    due = _shift(today.replace(day=1), -1)
    month = due.strftime("%Y-%m")
    written = conn.execute("SELECT 1 FROM monthly_letters WHERE month = ?", (month,)).fetchone() is not None
    return {"due_month": month, "due_label": _label(due), "written": written,
            "offer": not written and today.day <= OFFER_DAYS, "offer_days": OFFER_DAYS}


def write_letter(conn: sqlite3.Connection, month: str, today: Optional[date] = None) -> tuple[dict[str, Any], bool]:
    """Write and save one month's letter. A saved letter is returned unchanged, never rewritten."""
    existing = conn.execute("SELECT * FROM monthly_letters WHERE month = ?", (month,)).fetchone()
    if existing:
        return _row(existing), False
    letter = build_monthly_letter(conn, month, today=today)
    with conn:
        conn.execute("INSERT OR IGNORE INTO monthly_letters (month, letter_json) VALUES (?, ?)", (month, json.dumps(letter)))
    return _row(conn.execute("SELECT * FROM monthly_letters WHERE month = ?", (month,)).fetchone()), True
