"""Season in review: one calendar year of training on one page.

Everything here is read from data the app already keeps; there is no new
tracking. Each section reuses the service behind the page it links to, so the
numbers match: totals use the Dashboard year-chart query, records and lifts the
Records wall's progressions, mountains the Mountains page's coverage, goals the
Goals page's weekly windows. A section with nothing to show is left out rather
than filled with zeros.

The current year is offered from 1 December; past years with any activity are
always available. The closing coach paragraph, like the monthly letters, does
not call an LLM: it is written from the year's facts and the saved monthly
letters only when asked for, then saved and never rewritten.
"""

from __future__ import annotations

import json
import sqlite3
from collections import Counter
from datetime import date, datetime, timedelta
from typing import Any, Optional

from ..repositories import trails as trail_repo
from .goals import goal_value_for_window
from .guided_sessions import guided_completion_dates
from .personal_records import _iter_ranked, build_personal_records
from .trail_coverage import REGIONS

OFFER_MONTH = 12  # The current year is offered from 1 December.
MIN_STREAK_DAYS = 3
TOP_LIFTS = 5
SPORTS = (
    # key, label, activity types (None: everything not listed), distance shown
    ("ride", "Ride", ("Ride", "VirtualRide"), True),
    ("run", "Run", ("Run",), True),
    ("strength", "Strength", ("WeightTraining",), False),
    ("hike", "Hike", ("Hike",), True),
    ("walk", "Walk", ("Walk",), True),
    ("other", "Other", None, False),
)
LISTED_TYPES = tuple(kind for _, _, types, _ in SPORTS if types for kind in types)


def _plural(count: float, word: str) -> str:
    return f"{count:g} {word}{'' if count == 1 else 's'}"


def _hours(minutes: float) -> float:
    return round(minutes / 60.0, 1)


# ---------------------------------------------------------------------------
# Which years
# ---------------------------------------------------------------------------


def _years_with_data(conn: sqlite3.Connection) -> list[int]:
    return [int(row[0]) for row in conn.execute(
        "SELECT DISTINCT substr(date, 1, 4) FROM activities WHERE substr(date, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' ORDER BY 1 DESC"
    )]


def available_years(conn: sqlite3.Connection, today: Optional[date] = None) -> list[int]:
    """Past years with any activity, plus the current year from 1 December."""
    today = today or date.today()
    return [year for year in _years_with_data(conn)
            if year < today.year or (year == today.year and today.month >= OFFER_MONTH)]


def season_review_status(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    years = available_years(conn, today)
    return {"years": years, "current_offered": today.year in years, "offer_from": date(today.year, OFFER_MONTH, 1).isoformat()}


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _sport_totals(conn: sqlite3.Connection, year: int) -> dict[str, dict[str, Any]]:
    rows = conn.execute(
        "SELECT type, COUNT(*) AS sessions, COALESCE(SUM(duration_min), 0) AS minutes, "
        "COALESCE(SUM(distance_km), 0) AS km FROM activities WHERE substr(date, 1, 4) = ? GROUP BY type",
        (str(year),),
    ).fetchall()
    totals = {}
    for key, label, types, with_km in SPORTS:
        chosen = [row for row in rows if (row["type"] in types if types else row["type"] not in LISTED_TYPES)]
        sessions = sum(int(row["sessions"]) for row in chosen)
        if not sessions:
            continue
        totals[key] = {
            "key": key, "label": label, "sessions": sessions,
            "hours": _hours(sum(float(row["minutes"]) for row in chosen)),
            "km": round(sum(float(row["km"]) for row in chosen), 1) if with_km else None,
            "types": sorted(row["type"] for row in chosen),
        }
    return totals


def _sport_of(kind: str) -> str:
    return next((key for key, _, types, _ in SPORTS if types and kind in types), "other")


def _calendar(conn: sqlite3.Connection, year: int) -> tuple[list[dict], list[dict]]:
    """Month by month and day by day, for the page's year charts (same rows as the totals)."""
    rows = conn.execute(
        "SELECT substr(date, 1, 10) AS day, type, COUNT(*) AS sessions, COALESCE(SUM(duration_min), 0) AS minutes, "
        "COALESCE(SUM(distance_km), 0) AS km FROM activities WHERE substr(date, 1, 4) = ? GROUP BY day, type ORDER BY day",
        (str(year),),
    ).fetchall()
    months = [{"month": f"{year}-{index:02d}", "hours": 0.0, "sessions": 0, "sports": {}} for index in range(1, 13)]
    days: dict[str, dict[str, float]] = {}
    for row in rows:
        sport = _sport_of(row["type"])
        bucket = months[int(row["day"][5:7]) - 1]
        bucket["hours"] += row["minutes"] / 60.0
        bucket["sessions"] += int(row["sessions"])
        entry = bucket["sports"].setdefault(sport, {"hours": 0.0, "km": 0.0, "sessions": 0})
        entry["hours"] += row["minutes"] / 60.0
        entry["km"] += float(row["km"])
        entry["sessions"] += int(row["sessions"])
        days.setdefault(row["day"], {})
        days[row["day"]][sport] = days[row["day"]].get(sport, 0.0) + float(row["minutes"])
    for bucket in months:
        bucket["hours"] = round(bucket["hours"], 1)
        for entry in bucket["sports"].values():
            entry["hours"], entry["km"] = round(entry["hours"], 1), round(entry["km"], 1)
    calendar = [{"date": day, "minutes": round(sum(by_sport.values())), "sport": max(by_sport, key=by_sport.get)}
                for day, by_sport in days.items()]
    return months, calendar


def _active_days(conn: sqlite3.Connection, year: int) -> int:
    row = conn.execute("SELECT COUNT(DISTINCT substr(date, 1, 10)) FROM activities WHERE substr(date, 1, 4) = ?", (str(year),)).fetchone()
    return int(row[0] or 0)


def _change(now: Optional[float], before: Optional[float]) -> Optional[float]:
    if now is None or not before:
        return None
    return round((now - before) / before * 100)


def _totals(conn: sqlite3.Connection, year: int, today: date) -> dict[str, Any]:
    current = _sport_totals(conn, year)
    previous = _sport_totals(conn, year - 1)
    compare = bool(previous)  # Last year is compared only when it has any data.
    sports = []
    for key, item in current.items():
        before = previous.get(key)
        entry = dict(item)
        if compare:
            entry["previous"] = {k: before[k] for k in ("sessions", "hours", "km")} if before else None
            entry["change"] = {k: _change(item[k], before[k]) for k in ("sessions", "hours", "km")} if before else None
        sports.append(entry)
    total = {
        "sessions": sum(item["sessions"] for item in current.values()),
        "hours": round(sum(item["hours"] for item in current.values()), 1),
        "active_days": _active_days(conn, year),
    }
    if compare:
        before_total = {
            "sessions": sum(item["sessions"] for item in previous.values()),
            "hours": round(sum(item["hours"] for item in previous.values()), 1),
            "active_days": _active_days(conn, year - 1),
        }
        total["previous"] = before_total
        total["change"] = {k: _change(total[k], before_total[k]) for k in ("sessions", "hours", "active_days")}
    return {
        "sports": sports,
        "total": total,
        "previous_year": year - 1 if compare else None,
        # The current year in December is compared while it is still running.
        "to_date": year == today.year,
    }


def _longest_streak(conn: sqlite3.Connection, year: int) -> Optional[dict[str, Any]]:
    """Longest run of active days inside the year, counted like the Records wall's streaks."""
    prefix = str(year)
    keys = {row[0][:10] for row in conn.execute("SELECT DISTINCT date FROM activities WHERE substr(date, 1, 4) = ?", (prefix,))}
    keys |= {key for key in guided_completion_dates(conn) if key.startswith(prefix)}
    best: Optional[tuple[date, date]] = None
    run: Optional[tuple[date, date]] = None
    for day in sorted(date.fromisoformat(key) for key in keys):
        run = (run[0], day) if run and day == run[1] + timedelta(days=1) else (day, day)
        if best is None or (run[1] - run[0]) > (best[1] - best[0]):
            best = run
    if not best:
        return None
    days = (best[1] - best[0]).days + 1
    if days < MIN_STREAK_DAYS:
        return None
    return {"days": days, "start": best[0].isoformat(), "end": best[1].isoformat(),
            "links": [{"to": "/records", "label": "Streaks"}]}


def _year_steps(ranked: dict[str, Any], start: str, end: str) -> Optional[tuple[dict, dict, int]]:
    """(baseline, best in the year, records set) when an all-time best was beaten during the year.

    The baseline is the best before the year, or the year's first attempt when
    the record is new this year: a first ever attempt beats nothing.
    """
    steps = [step for step in ranked.get("progression") or [] if step["date"][:10] <= end]
    before = [step for step in steps if step["date"][:10] < start]
    during = [step for step in steps if step["date"][:10] >= start]
    if before and during:
        return before[-1], during[-1], len(during)
    if len(during) >= 2:
        return during[0], during[-1], len(during) - 1
    return None


def _records(records: dict[str, Any], year: int) -> tuple[list[dict], list[dict]]:
    start, end = f"{year}-01-01", f"{year}-12-31"
    endurance, lifts = [], []
    for category, label, ranked in _iter_ranked(records):
        found = _year_steps(ranked, start, end)
        if not found:
            continue
        baseline, best, count = found
        item = {
            "category": category, "label": label, "display": best["display"], "date": best["date"][:10],
            "activity_id": best.get("activity_id"), "from": baseline["display"], "from_date": baseline["date"][:10],
            "new_this_year": baseline["date"][:10] >= start, "times": count,
            # Times get smaller and watts bigger, so the size of the step is the absolute change.
            "improvement_percent": round(abs(best["value"] - baseline["value"]) / baseline["value"] * 100, 1) if baseline["value"] else None,
        }
        if category == "Lift":
            gain = best["value"] - baseline["value"]
            if gain <= 0:
                continue
            item.update({
                "metric_label": ranked.get("metric_label"), "key_lift": bool(ranked.get("key_lift")),
                "gain": round(gain, 1), "gain_percent": round(gain / baseline["value"] * 100, 1) if baseline["value"] else None,
                "unit": "reps" if ranked.get("metric") == "reps" else "kg",
            })
            lifts.append(item)
        else:
            endurance.append(item)
    order = {name: index for index, name in enumerate(("Bike power", "Bike distance", "Indoor bike distance", "Run"))}
    endurance.sort(key=lambda item: (order.get(item["category"], 9), item["date"]))
    # Loaded lifts first: a jump in bodyweight reps is not the same kind of progress.
    lifts.sort(key=lambda item: (item["unit"] != "kg", -(item["gain_percent"] or 0), item["label"]))
    return endurance, lifts[:TOP_LIFTS]


def _mountains(conn: sqlite3.Connection, year: int) -> list[dict[str, Any]]:
    """Trail and summits first reached this year, counted like the Mountains page (national parks only)."""
    prefix, regions = str(year), []
    for key, region in REGIONS.items():
        try:
            sections = trail_repo.list_sections(conn, key)
            pois = trail_repo.list_pois(conn, key)
        except sqlite3.OperationalError:
            return []
        in_park = [section for section in sections if not section["around"]]
        total_m = sum(section["length_m"] for section in in_park)
        gained = [section for section in in_park if section["status"] == "done" and (section["first_walked_on"] or "").startswith(prefix)]
        done_by_end = [section for section in in_park if section["status"] == "done" and (section["first_walked_on"] or "") <= f"{year}-12-31"]
        summits = sorted(
            (poi for poi in pois if poi["kind"] == "peak" and not poi["around"] and (poi["first_visited_on"] or "").startswith(prefix)),
            key=lambda poi: (-(poi["ele"] or 0), poi["name"]),
        )
        gained_m = sum(section["length_m"] for section in gained)
        if not gained and not summits:
            continue
        regions.append({
            "key": key, "name": region["name"],
            "gained_km": round(gained_m / 1000, 1),
            "gained_pct": round(gained_m / total_m * 100, 1) if total_m else None,
            "done_pct_end": round(sum(section["length_m"] for section in done_by_end) / total_m * 100) if total_m else None,
            "summits": [{"name": poi["name"], "ele": poi["ele"], "date": poi["first_visited_on"]} for poi in summits],
            "links": [{"to": f"/mountains/{key}", "label": "Mountains"}],
        })
    return regions


def _best_month(conn: sqlite3.Connection, year: int) -> Optional[dict[str, Any]]:
    """The month with the most training hours (walks excluded, like the monthly letters)."""
    rows = conn.execute(
        "SELECT substr(date, 1, 7) AS month, COALESCE(SUM(duration_min), 0) AS minutes, COUNT(*) AS sessions, "
        "COUNT(DISTINCT substr(date, 1, 10)) AS active_days FROM activities "
        "WHERE substr(date, 1, 4) = ? AND type != 'Walk' GROUP BY month",
        (str(year),),
    ).fetchall()
    months = [row for row in rows if row["minutes"]]
    if len(months) < 2:
        return None  # One month of data has no "best".
    best = max(months, key=lambda row: (row["minutes"], row["sessions"]))
    month_start = datetime.strptime(best["month"], "%Y-%m").date()
    letter = conn.execute("SELECT 1 FROM monthly_letters WHERE month = ?", (best["month"],)).fetchone()
    links = [{"to": "/calendar", "label": "Calendar"}]
    if letter:
        links.append({"to": "/weekly-review", "label": "Monthly letter"})
    return {"month": best["month"], "label": month_start.strftime("%B"), "hours": _hours(best["minutes"]),
            "sessions": int(best["sessions"]), "active_days": int(best["active_days"]), "links": links}


def _weekly_goal_kept(conn: sqlite3.Connection, goal: sqlite3.Row, year: int, today: date) -> Optional[dict[str, Any]]:
    """Full weeks in the year since the goal started, and how many met the target."""
    target = float(goal["target_value"] or 0)
    first = max(date(year, 1, 1), date.fromisoformat(goal["start_date"][:10]))
    last = min(date(year, 12, 31), today - timedelta(days=1))
    monday = first + timedelta(days=(7 - first.weekday()) % 7)
    weeks = kept = 0
    while target and monday + timedelta(days=6) <= last:
        weeks += 1
        value = goal_value_for_window(conn, goal, start_date=monday.isoformat(), end_date=(monday + timedelta(days=6)).isoformat())
        kept += value >= target
        monday += timedelta(days=7)
    if not weeks:
        return None
    return {"goal_id": goal["id"], "title": goal["title"], "kept": kept, "weeks": weeks,
            "anchor": goal["commitment"] == "anchor", "target": target}


def _goals(conn: sqlite3.Connection, year: int, today: date) -> Optional[dict[str, Any]]:
    prefix = str(year)
    try:
        rows = conn.execute("SELECT * FROM goals ORDER BY CASE commitment WHEN 'anchor' THEN 0 ELSE 1 END, id").fetchall()
    except sqlite3.Error:
        return None
    completed = []
    weekly = []
    for goal in rows:
        status = goal["lifecycle_status"] or "active"
        if status == "completed":
            when = (goal["status_changed_at"] or goal["end_date"] or "")[:10]
            if when.startswith(prefix):
                completed.append({"goal_id": goal["id"], "title": goal["title"], "date": when})
        elif goal["period_type"] == "week" and status == "active" and goal["is_active"]:
            try:
                kept = _weekly_goal_kept(conn, goal, year, today)
            except (sqlite3.Error, ValueError, TypeError, KeyError):
                kept = None
            if kept:
                weekly.append(kept)
    if not completed and not weekly:
        return None
    return {"completed": completed, "weekly": weekly, "links": [{"to": "/goals", "label": "Goals"}]}


def _letters(conn: sqlite3.Connection, year: int) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT month, letter_json FROM monthly_letters WHERE month LIKE ? ORDER BY month", (f"{year}-%",)).fetchall()
    return [{"month": row["month"], **json.loads(row["letter_json"])} for row in rows]


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


def build_season_review(conn: sqlite3.Connection, year: int, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    if year not in available_years(conn, today):
        if year == today.year:
            raise ValueError(f"The {year} season review opens on 1 December")
        raise ValueError(f"No activities recorded in {year}")
    as_of = min(date(year, 12, 31), today)
    records, lifts = _records(build_personal_records(conn, today=as_of), year)
    letters = _letters(conn, year)
    months, days = _calendar(conn, year)
    return {
        "year": year,
        "as_of": as_of.isoformat(),
        "complete": year < today.year,
        "years": available_years(conn, today),
        "totals": _totals(conn, year, today),
        "months": months,
        "days": days,
        "streak": _longest_streak(conn, year),
        "records": records,
        "lifts": lifts,
        "mountains": _mountains(conn, year),
        "best_month": _best_month(conn, year),
        "goals": _goals(conn, year, today),
        "letters": [{"month": item["month"], "label": item.get("label")} for item in letters],
        "coach": saved_coach_paragraph(conn, year),
    }


# ---------------------------------------------------------------------------
# Coach paragraph
# ---------------------------------------------------------------------------


def _record_phrase(review: dict[str, Any]) -> Optional[str]:
    parts = []
    records = review["records"]
    if records:
        top = max(records, key=lambda item: item["improvement_percent"] or 0)
        name = top["label"] if top["label"].startswith(("Longest", "Biggest")) else f"{top['category'].lower()} {top['label']}"
        more = f" and {_plural(len(records) - 1, 'other best')}" if len(records) > 1 else ""
        parts.append(f"{name} from {top['from']} to {top['display']}{more}")
    if review["lifts"]:
        lift = review["lifts"][0]
        parts.append(f"{lift['label']} from {lift['from']} to {lift['display']}")
    return "; ".join(parts) if parts else None


def write_coach_paragraph_text(review: dict[str, Any], letters: list[dict[str, Any]]) -> dict[str, Any]:
    year = review["year"]
    total = review["totals"]["total"]
    sentences = [f"{year} came to {_plural(total['sessions'], 'session')} and {total['hours']:g} hours over {total['active_days']} active days"]
    change = (total.get("change") or {}).get("hours")
    if change is not None and abs(change) >= 5:
        sentences[-1] += f", {abs(change):g}% {'more' if change > 0 else 'less'} time than {year - 1}"
    sentences[-1] += "."
    if review["streak"]:
        sentences.append(f"The longest run was {review['streak']['days']} days in a row.")
    best = _record_phrase(review)
    if best:
        sentences.append(f"The biggest steps: {best}.")
    summits = sum(len(region["summits"]) for region in review["mountains"])
    trail_km = sum(region["gained_km"] for region in review["mountains"])
    if summits or trail_km:
        bits = [f"{trail_km:g} km of new trail"] if trail_km else []
        bits += [_plural(summits, "new summit")] if summits else []
        sentences.append(f"In the mountains: {' and '.join(bits)}.")
    goals = review["goals"] or {}
    anchor = next((item for item in goals.get("weekly", []) if item["anchor"]), None)
    if anchor:
        sentences.append(f"{anchor['title']} held in {anchor['kept']} of {anchor['weeks']} weeks.")
    for goal in goals.get("completed", [])[:2]:
        sentences.append(f"{goal['title']}: done.")
    # The monthly letters say what kept coming up across the year.
    win_kinds = Counter(win["kind"] for letter in letters for win in letter.get("wins", []))
    themes = {"record": "new bests", "streak": "streaks", "consistency": "steady volume", "goal": "goals kept"}
    if win_kinds:
        kind, count = win_kinds.most_common(1)[0]
        sentences.append(f"Across {_plural(len(letters), 'monthly letter')}, the wins kept coming back to {themes.get(kind, kind)} ({count}×).")
    focus = next((letter["focus"] for letter in reversed(letters) if letter.get("focus")), None)
    if focus and focus.get("source") != "default":
        sentences.append(f"Into the winter, carry the last letter's focus: {focus['headline'].rstrip('.')}.")
    else:
        sentences.append("Into the winter: keep the rhythm that built this year before adding anything.")
    return {"text": " ".join(sentences), "letters_used": [letter["month"] for letter in letters]}


def saved_coach_paragraph(conn: sqlite3.Connection, year: int) -> Optional[dict[str, Any]]:
    row = conn.execute("SELECT coach_json, created_at FROM season_reviews WHERE year = ?", (year,)).fetchone()
    return {**json.loads(row["coach_json"]), "created_at": row["created_at"]} if row else None


def write_coach_paragraph(conn: sqlite3.Connection, year: int, today: Optional[date] = None) -> tuple[dict[str, Any], bool]:
    """Write and save the year's coach paragraph. A saved paragraph is returned unchanged, never rewritten."""
    existing = saved_coach_paragraph(conn, year)
    if existing:
        return existing, False
    review = build_season_review(conn, year, today=today)
    paragraph = write_coach_paragraph_text(review, _letters(conn, year))
    with conn:
        conn.execute("INSERT OR IGNORE INTO season_reviews (year, coach_json) VALUES (?, ?)", (year, json.dumps(paragraph)))
    return saved_coach_paragraph(conn, year), True
