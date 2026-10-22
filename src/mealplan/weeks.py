"""ISO-week helpers. A week id looks like 2026-W44 and always starts on Monday."""

from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

WEEK_RE = re.compile(r"^(\d{4})-W(\d{2})$")
DOW_SHORT = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")


def today_in(tz: str) -> date:
    return datetime.now(ZoneInfo(tz)).date()


def week_id(d: date) -> str:
    y, w, _ = d.isocalendar()
    return f"{y}-W{w:02d}"


def week_start(week: str) -> date:
    m = WEEK_RE.match(week)
    if not m:
        raise ValueError(f"bad week id {week!r}; expected YYYY-Www")
    return date.fromisocalendar(int(m.group(1)), int(m.group(2)), 1)


def week_dates(week: str) -> list[date]:
    start = week_start(week)
    return [start + timedelta(days=i) for i in range(7)]


def resolve_week(spec: str, tz: str, today: date | None = None) -> str:
    """'this' | 'next' | 'last' | 'YYYY-Www' -> 'YYYY-Www'."""
    today = today or today_in(tz)
    spec = spec.strip().lower()
    if spec == "this":
        return week_id(today)
    if spec == "next":
        return week_id(today + timedelta(days=7))
    if spec == "last":
        return week_id(today - timedelta(days=7))
    upper = spec.upper()
    if WEEK_RE.match(upper):
        week_start(upper)  # validates
        return upper
    raise ValueError(f"bad week {spec!r}; use this, next, last or YYYY-Www")


def dow_short(d: date) -> str:
    return DOW_SHORT[d.weekday()]


def is_weekend(d: date) -> bool:
    return d.weekday() >= 5
