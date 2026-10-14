"""Season in review: one calendar year of training on one page.

Everything here is read from data the app already keeps; there is no new
tracking. Each section reuses the service behind the page it links to, so the
numbers match: totals use the Dashboard year-chart query, records and lifts the
Records wall's progressions, mountains the Mountains page's coverage, goals the
Goals page's weekly windows. A section with nothing to show is left out rather
than filled with zeros.

Every year with activity is available, the running year shown "so far". The
closing coach paragraph, like the monthly letters, does
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
from .mountain_trips import list_trips
from .personal_records import _iter_ranked, build_personal_records
from .trail_coverage import REGIONS

COACH_OPENS_MONTH = 12  # The running year's coach paragraph is saved once, so it waits for December.
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
    """Every year with any activity, the running year included (shown "so far")."""
    today = today or date.today()
    return [year for year in _years_with_data(conn) if year <= today.year]


class CoachNotOpen(ValueError):
    """The running year's paragraph is asked for before December."""


def coach_opens_on(year: int, today: date) -> Optional[str]:
    """When the year's coach paragraph can be written; None once it can."""
    if year < today.year or today.month >= COACH_OPENS_MONTH:
        return None
    return date(year, COACH_OPENS_MONTH, 1).isoformat()


def season_review_status(conn: sqlite3.Connection, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    years = available_years(conn, today)
    return {"years": years, "current_included": today.year in years, "coach_opens_on": coach_opens_on(today.year, today)}


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------


def _sport_totals(conn: sqlite3.Connection, year: int, until: str = "12-31") -> dict[str, dict[str, Any]]:
    """Totals by sport from 1 January to ``until`` ("MM-DD") of the year."""
    rows = conn.execute(
        "SELECT type, COUNT(*) AS sessions, COALESCE(SUM(duration_min), 0) AS minutes, "
        "COALESCE(SUM(distance_km), 0) AS km FROM activities WHERE substr(date, 1, 4) = ? AND substr(date, 6, 5) <= ? GROUP BY type",
        (str(year), until),
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


def _active_days(conn: sqlite3.Connection, year: int, until: str = "12-31") -> int:
    row = conn.execute(
        "SELECT COUNT(DISTINCT substr(date, 1, 10)) FROM activities WHERE substr(date, 1, 4) = ? AND substr(date, 6, 5) <= ?",
        (str(year), until),
    ).fetchone()
    return int(row[0] or 0)


def _change(now: Optional[float], before: Optional[float]) -> Optional[float]:
    if now is None or not before:
        return None
    return round((now - before) / before * 100)


def _hours_until(conn: sqlite3.Connection, year: int, until: str) -> float:
    row = conn.execute(
        "SELECT COALESCE(SUM(duration_min), 0) FROM activities WHERE substr(date, 1, 4) = ? AND substr(date, 6, 5) <= ?",
        (str(year), until),
    ).fetchone()
    return _hours(float(row[0] or 0))


def _pace(conn: sqlite3.Connection, year: int, until: str, hours_now: float) -> Optional[dict[str, Any]]:
    """The running year against the best other year at the same date."""
    row = conn.execute(
        "SELECT substr(date, 1, 4) AS year, SUM(duration_min) AS minutes FROM activities "
        "WHERE substr(date, 1, 4) != ? AND substr(date, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' GROUP BY 1 ORDER BY minutes DESC LIMIT 1",
        (str(year),),
    ).fetchone()
    if not row or not row["minutes"]:
        return None
    best = int(row["year"])
    then = _hours_until(conn, best, until)
    return {"year": best, "hours": then, "full_hours": _hours(float(row["minutes"])), "delta": round(hours_now - then, 1)}


def _totals(conn: sqlite3.Connection, year: int, today: date) -> dict[str, Any]:
    # While the year runs, it is compared with the same dates last year, not with a full year.
    to_date = year == today.year
    until = today.strftime("%m-%d") if to_date else "12-31"
    current = _sport_totals(conn, year)
    previous = _sport_totals(conn, year - 1, until)
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
            "active_days": _active_days(conn, year - 1, until),
        }
        total["previous"] = before_total
        total["change"] = {k: _change(total[k], before_total[k]) for k in ("sessions", "hours", "active_days")}
    return {
        "sports": sports,
        "total": total,
        "previous_year": year - 1 if compare else None,
        "to_date": to_date,
        "compared_until": until if to_date else None,
        "pace": _pace(conn, year, until, total["hours"]) if to_date else None,
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
            "value": best["value"], "from_value": baseline["value"], "higher_is_better": ranked.get("higher_is_better", True),
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


SEASON_BEST_CATEGORIES = ("Run", "Bike distance", "Bike power")  # Lifts have their own section; indoor distance is simulated.
SEASON_BEST_MIN_GAP = 2
SEASON_BEST_MIN_SEASONS = 3  # "Best since 2013" means little when only two seasons have the effort.


def _season_bests(records: dict[str, Any], year: int, already: set[tuple[str, str]]) -> list[dict[str, Any]]:
    """The year's best in each record, framed against every other season.

    Records already listed as new all-time bests are left out; what remains
    says how a season compares when it did not beat the all-time record:
    best since an earlier year, or its place among all seasons.
    """
    key = str(year)
    found = []
    for category, label, ranked in _iter_ranked(records):
        if category not in SEASON_BEST_CATEGORIES or (category, label) in already:
            continue
        yearly = ranked.get("yearly") or {}
        best = yearly.get(key)
        if not best:
            continue
        higher = ranked.get("higher_is_better", True)
        better = lambda other: other["value"] > best["value"] if higher else other["value"] < best["value"]
        beaten_by = sorted(int(other_year) for other_year, other in yearly.items() if other_year != key and better(other))
        seasons = len(yearly)
        earlier = [other for other in beaten_by if other < year]
        later = [other for other in beaten_by if other > year]
        item = {"category": category, "label": label, "display": best["display"], "detail": best.get("detail"),
                "date": best["date"][:10], "activity_id": best.get("activity_id"), "seasons": seasons, "rank": len(beaten_by) + 1,
                "higher_is_better": higher,
                # Every season's best, oldest first, so the year can be drawn among the others.
                "history": [{"year": int(other_year), "value": other["value"], "display": other["display"]}
                            for other_year, other in sorted(yearly.items())]}
        if seasons == 1:
            continue  # Only one season has this record: nothing to compare.
        if not beaten_by:
            item.update(kind="best_ever", headline="Best of any season", score=4)
        elif seasons < SEASON_BEST_MIN_SEASONS:
            continue
        elif not earlier:
            item.update(kind="best_then", headline=f"Best season yet, until {later[0]}", score=3)
        elif year - earlier[-1] >= SEASON_BEST_MIN_GAP:
            item.update(kind="since", headline=f"Best since {earlier[-1]}", score=2 + (year - earlier[-1]) / 100)
        elif item["rank"] <= 3:
            item.update(kind="rank", headline=f"#{item['rank']} of {seasons} seasons", score=1)
        else:
            continue
        found.append(item)
    order = {name: index for index, name in enumerate(SEASON_BEST_CATEGORIES)}
    found.sort(key=lambda item: (-item["score"], order[item["category"]], item["date"]))
    return [{k: v for k, v in item.items() if k != "score"} for item in found]


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
# Career: the year against every other year
# ---------------------------------------------------------------------------

RANKED = (
    # key, label, unit
    ("hours", "Most hours", "h"),
    ("active_days", "Most active days", ""),
    ("sessions", "Most sessions", ""),
    ("ride_km", "Most riding", "km"),
    ("run_km", "Most running", "km"),
    ("strength", "Most strength sessions", ""),
)
MILESTONES = (
    # key, unit label, thresholds
    ("run_km", "km of running", (1000, 2500, 5000, 7500, 10000, 15000, 20000, 25000, 30000, 40000, 50000)),
    ("ride_km", "km of riding", (1000, 2500, 5000, 7500, 10000, 15000, 20000, 25000, 30000, 40000, 50000)),
    ("activities", "activities", (100, 250, 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000, 7500, 10000)),
    ("hours", "hours of training", (100, 250, 500, 1000, 1500, 2000, 2500, 3000, 4000, 5000)),
)
MAX_BADGES = 4
SINCE_MIN_GAP = 3  # "Most since 2024" a year later says little.
SINCE_MIN_SHARE = 0.25  # Nor do "since" or "#2" badges for 2 sessions against a best of 148.


def _career_rows(conn: sqlite3.Connection) -> list[sqlite3.Row]:
    return conn.execute(
        "SELECT id, substr(date, 1, 10) AS day, type, name, COALESCE(duration_min, 0) AS minutes, "
        "COALESCE(distance_km, 0) AS km FROM activities "
        "WHERE substr(date, 1, 4) GLOB '[0-9][0-9][0-9][0-9]' ORDER BY date, created_at, id"
    ).fetchall()


def _career_years(rows: list[sqlite3.Row], available: list[int]) -> list[dict[str, Any]]:
    """Every year from the first activity to the last, gaps included, with hours by sport."""
    if not rows:
        return []
    years: dict[int, dict[str, Any]] = {}
    days: dict[int, set] = {}
    for row in rows:
        year = int(row["day"][:4])
        item = years.setdefault(year, {"hours": 0.0, "sessions": 0, "ride_km": 0.0, "run_km": 0.0, "strength": 0, "sports": {}})
        sport = _sport_of(row["type"])
        item["hours"] += row["minutes"] / 60.0
        item["sessions"] += 1
        item["sports"][sport] = item["sports"].get(sport, 0.0) + row["minutes"] / 60.0
        if sport == "ride":
            item["ride_km"] += row["km"]
        elif sport == "run":
            item["run_km"] += row["km"]
        elif sport == "strength":
            item["strength"] += 1
        days.setdefault(year, set()).add(row["day"])
    first, last = min(years), max(years)
    result = []
    for year in range(first, last + 1):
        item = years.get(year, {"hours": 0.0, "sessions": 0, "ride_km": 0.0, "run_km": 0.0, "strength": 0, "sports": {}})
        result.append({
            "year": year, "available": year in available,
            "hours": round(item["hours"], 1), "sessions": item["sessions"], "active_days": len(days.get(year, ())),
            "ride_km": round(item["ride_km"], 1), "run_km": round(item["run_km"], 1), "strength": item["strength"],
            "sports": {key: round(value, 1) for key, value in item["sports"].items()},
        })
    return result


def _format(value: float, unit: str) -> str:
    text = f"{round(value):,}" if value >= 100 or float(value).is_integer() else f"{value:,.1f}"
    return f"{text} {unit}".strip()


def _badges(career: list[dict[str, Any]], year: int, to_date: bool) -> list[dict[str, Any]]:
    """Where the year stands among all years: records, records at the time, best since, top three."""
    found = []
    others = [item for item in career if item["sessions"]]
    current = next((item for item in others if item["year"] == year), None)
    if not current or len(others) < 2:
        return []
    for key, label, unit in RANKED:
        value = current[key]
        if not value:
            continue
        values = {item["year"]: item[key] for item in others}
        rank = 1 + sum(1 for other in values.values() if other > value)
        earlier = {y: v for y, v in values.items() if y < year}
        later_beat = sorted(y for y, v in values.items() if y > year and v > value)
        so_far = " so far" if to_date else ""
        if rank == 1:
            best_other_year, best_other = max(((y, v) for y, v in values.items() if y != year), key=lambda pair: pair[1])
            detail = f"{_format(value, unit)}{so_far}" + (f" · previous best {_format(best_other, unit)} in {best_other_year}" if best_other else "")
            found.append({"kind": "record", "metric": key, "headline": f"{label} of any year", "detail": detail, "score": 4})
        elif earlier and value > max(earlier.values()):
            detail = f"{_format(value, unit)} · a record until {later_beat[0]}"
            found.append({"kind": "record_then", "metric": key, "headline": f"{label} up to then", "detail": detail, "score": 3})
        else:
            since = max((y for y, v in earlier.items() if v > value), default=None)
            if since is not None and year - since >= SINCE_MIN_GAP and value >= SINCE_MIN_SHARE * max(values.values()):
                found.append({"kind": "since", "metric": key, "headline": f"{label} since {since}",
                              "detail": f"{_format(value, unit)}{so_far} · #{rank} of {len(values)} years", "score": 2})
            elif rank <= 3 and value >= SINCE_MIN_SHARE * max(values.values()):
                found.append({"kind": "rank", "metric": key, "headline": f"#{rank} of {len(values)} years for {label[5:].lower()}",
                              "detail": f"{_format(value, unit)}{so_far}", "score": 1})
    found.sort(key=lambda item: -item["score"])
    return [{k: v for k, v in item.items() if k != "score"} for item in found[:MAX_BADGES]]


def _milestones(rows: list[sqlite3.Row], year: int) -> list[dict[str, Any]]:
    """Lifetime totals that crossed a round number during the year, with the activity that did it."""
    totals = {"run_km": 0.0, "ride_km": 0.0, "activities": 0, "hours": 0.0}
    found = []
    for row in rows:
        row_year = int(row["day"][:4])
        if row_year > year:
            break
        before = dict(totals)
        sport = _sport_of(row["type"])
        totals["activities"] += 1
        totals["hours"] += row["minutes"] / 60.0
        if sport == "run":
            totals["run_km"] += row["km"]
        elif sport == "ride":
            totals["ride_km"] += row["km"]
        if row_year != year:
            continue
        for key, unit, thresholds in MILESTONES:
            for threshold in thresholds:
                if before[key] < threshold <= totals[key]:
                    found.append({"kind": key, "value": threshold, "unit": unit, "date": row["day"],
                                  "activity_id": row["id"], "activity_name": row["name"]})
    return found


def _career(conn: sqlite3.Connection, year: int, today: date) -> dict[str, Any]:
    rows = _career_rows(conn)
    years = _career_years(rows, available_years(conn, today))
    return {"years": years, "badges": _badges(years, year, year == today.year), "milestones": _milestones(rows, year)}


# ---------------------------------------------------------------------------
# Review
# ---------------------------------------------------------------------------


def build_season_review(conn: sqlite3.Connection, year: int, today: Optional[date] = None) -> dict[str, Any]:
    today = today or date.today()
    if year not in available_years(conn, today):
        raise ValueError(f"No activities recorded in {year}")
    as_of = min(date(year, 12, 31), today)
    record_data = build_personal_records(conn, today=as_of, include_yearly=True)
    records, lifts = _records(record_data, year)
    season_bests = _season_bests(record_data, year, {(item["category"], item["label"]) for item in records})
    letters = _letters(conn, year)
    months, days = _calendar(conn, year)
    return {
        "year": year,
        "as_of": as_of.isoformat(),
        "complete": year < today.year,
        "years": available_years(conn, today),
        "totals": _totals(conn, year, today),
        "career": _career(conn, year, today),
        "months": months,
        "days": days,
        "streak": _longest_streak(conn, year),
        "records": records,
        "season_bests": season_bests,
        "lifts": lifts,
        "mountains": _mountains(conn, year),
        "mountain_trips": [trip for trip in list_trips(conn, today)["trips"] if trip["start_date"].startswith(str(year))],
        "best_month": _best_month(conn, year),
        "goals": _goals(conn, year, today),
        "letters": [{"month": item["month"], "label": item.get("label")} for item in letters],
        "coach": saved_coach_paragraph(conn, year),
        "coach_opens_on": coach_opens_on(year, today),
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


COMEBACK_LOOKBACK_YEARS = 6
COMEBACK_FACTOR = 4  # This year needs four times the low year's sessions to call it a comeback.
MILESTONE_ORDER = ("ride_km", "run_km", "activities", "hours")


def _season_best_phrase(item: dict[str, Any]) -> str:
    """'Your longest ride (126.0 km)', 'Your fastest 10K run (45:02)', 'Your best 20 min power (230 W)'."""
    label = item["label"]
    if label.startswith(("Longest", "Biggest")):
        return f"Your {label[0].lower()}{label[1:]} ({item['display']})"
    if item["category"] == "Bike power":
        return f"Your best {label} power ({item['display']})"
    sport = "run" if item["category"] == "Run" else "ride"
    return f"Your fastest {label} {sport} ({item['display']})"


def _career_sentences(review: dict[str, Any]) -> list[str]:
    """The year in the context of every year: records, a comeback, the biggest milestone, a season best."""
    career = review.get("career") or {}
    year = review["year"]
    years = [item for item in career.get("years", []) if item["sessions"]]
    sentences = []
    hours_badge = next((badge for badge in career.get("badges", []) if badge["metric"] == "hours"), None)
    if hours_badge and hours_badge["kind"] == "record" and years:
        others = [item for item in years if item["year"] != year]
        best = max(others, key=lambda item: item["hours"]) if others else None
        tail = f", past {best['year']}'s {round(best['hours']):g} h" if best else ""
        sentences.append(f"Your biggest year since you started in {years[0]['year']}{tail}.")
    elif hours_badge and hours_badge["kind"] == "since":
        sentences.append(f"{hours_badge['headline']}.")
    now = next((item for item in years if item["year"] == year), None)
    window = [item for item in career.get("years", []) if year - COMEBACK_LOOKBACK_YEARS <= item["year"] < year]
    if now and window and any(item["year"] < window[0]["year"] for item in years):
        low = min(window, key=lambda item: (item["sessions"], -item["year"]))  # The latest low point.
        if low["sessions"] * COMEBACK_FACTOR <= now["sessions"]:
            count = _plural(low["sessions"], "session") if low["sessions"] else "nothing logged"
            sentences.append(f"A full comeback from {count} in {low['year']}.")
    other_record = next((badge for badge in career.get("badges", []) if badge["kind"] == "record" and badge["metric"] in ("ride_km", "run_km")), None)
    if other_record:
        sentences.append(f"{other_record['headline']}: {other_record['detail'].split(' · ')[0].replace(' so far', '')}.")
    milestones = sorted(career.get("milestones", []), key=lambda item: (MILESTONE_ORDER.index(item["kind"]), -item["value"]))
    if milestones:
        top = milestones[0]
        sentences.append(f"You passed {top['value']:,} {top['unit']} on {date.fromisoformat(top['date']).strftime('%-d %b')}.")
    since = next((item for item in review.get("season_bests", []) if item["kind"] == "since"), None)
    if since:
        sentences.append(f"{_season_best_phrase(since)} was the best since {since['headline'].rsplit(' ', 1)[-1]}.")
    return sentences


def write_coach_paragraph_text(review: dict[str, Any], letters: list[dict[str, Any]]) -> dict[str, Any]:
    year = review["year"]
    total = review["totals"]["total"]
    sentences = [f"{year} came to {_plural(total['sessions'], 'session')} and {total['hours']:g} hours over {total['active_days']} active days"]
    change = (total.get("change") or {}).get("hours")
    if change is not None and abs(change) >= 5:
        sentences[-1] += f", {abs(change):g}% {'more' if change > 0 else 'less'} time than {year - 1}"
    sentences[-1] += "."
    sentences += _career_sentences(review)
    if review["streak"]:
        sentences.append(f"The longest streak was {review['streak']['days']} days in a row.")
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


def write_coach_paragraph(conn: sqlite3.Connection, year: int, today: Optional[date] = None, *, rewrite: bool = False) -> tuple[dict[str, Any], bool]:
    """Write and save the year's coach paragraph.

    A saved paragraph is returned unchanged unless ``rewrite`` is asked for
    explicitly; a rewrite keeps the text it replaced as ``previous``.
    """
    existing = saved_coach_paragraph(conn, year)
    if existing and not rewrite:
        return existing, False
    opens = coach_opens_on(year, today or date.today())
    if opens:
        raise CoachNotOpen(f"The {year} coach paragraph can be written from 1 December, once most of the year is in")
    review = build_season_review(conn, year, today=today)
    paragraph = write_coach_paragraph_text(review, _letters(conn, year))
    if existing:
        paragraph["previous"] = {"text": existing["text"], "created_at": existing["created_at"]}
    with conn:
        conn.execute(
            "INSERT INTO season_reviews (year, coach_json) VALUES (?, ?) "
            "ON CONFLICT(year) DO UPDATE SET coach_json = excluded.coach_json, created_at = CURRENT_TIMESTAMP",
            (year, json.dumps(paragraph)),
        )
    return saved_coach_paragraph(conn, year), True
