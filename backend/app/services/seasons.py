"""Training seasons: which months are the athlete's off season.

Riding and running volume swing with the weather (indoor winters, outdoor
summers), so goal reviews compare like with like: a winter week is judged
against past winter weeks, not the summer that preceded it.
"""

import calendar
from datetime import date, timedelta
from typing import Iterable, Optional

# Poland-style default: indoor riding from October through March.
DEFAULT_OFF_SEASON_MONTHS = (10, 11, 12, 1, 2, 3)
SEASON_LABELS = {"off": "off season", "main": "main season"}


def normalize_off_season_months(value: Optional[Iterable]) -> list[int]:
    if value is None:
        return list(DEFAULT_OFF_SEASON_MONTHS)
    months = []
    for item in value:
        try:
            month = int(item)
        except (TypeError, ValueError):
            continue
        if 1 <= month <= 12 and month not in months:
            months.append(month)
    return months


def season_for(day: date, off_months: Iterable[int]) -> str:
    return "off" if day.month in set(off_months) else "main"


def season_label(off_months: Iterable[int]) -> str:
    """'Oct–Mar' for a contiguous (possibly year-wrapping) block of months."""
    months = sorted(set(off_months))
    if not months:
        return "None"
    if len(months) == 12:
        return "All year"
    # Start at the month whose predecessor is not in the season.
    start = next((month for month in months if (month - 2) % 12 + 1 not in months), months[0])
    end = start
    while end % 12 + 1 in months and end % 12 + 1 != start:
        end = end % 12 + 1
    if len(months) != ((end - start) % 12) + 1:
        return ", ".join(calendar.month_abbr[month] for month in months)
    return f"{calendar.month_abbr[start]}–{calendar.month_abbr[end]}"


def _month_end(day: date) -> date:
    return day.replace(day=calendar.monthrange(day.year, day.month)[1])


def off_season_end(today: date, off_months: Iterable[int]) -> Optional[date]:
    """Last day of the current off season, or of the next one when in main season."""
    months = set(off_months)
    if not months or len(months) == 12:
        return None
    cursor = today.replace(day=1)
    started = today.month in months
    for _ in range(24):
        in_season = cursor.month in months
        started = started or in_season
        next_month = _month_end(cursor) + timedelta(days=1)
        if started and in_season and next_month.month not in months:
            return _month_end(cursor)
        cursor = next_month
    return None


def next_season_change(today: date, off_months: Iterable[int]) -> Optional[date]:
    months = set(off_months)
    if not months or len(months) == 12:
        return None
    current = season_for(today, months)
    cursor = _month_end(today) + timedelta(days=1)
    for _ in range(12):
        if season_for(cursor, months) != current:
            return cursor
        cursor = _month_end(cursor) + timedelta(days=1)
    return None
