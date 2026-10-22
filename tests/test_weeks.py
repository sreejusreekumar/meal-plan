from datetime import date

import pytest

from mealplan.weeks import resolve_week, week_dates, week_id, week_start

TZ = "Australia/Melbourne"


def test_week_id_and_start_roundtrip():
    assert week_id(date(2026, 10, 23)) == "2026-W43"
    assert week_start("2026-W43") == date(2026, 10, 19)
    assert week_start("2026-W44") == date(2026, 10, 26)


def test_resolve_specs():
    today = date(2026, 10, 23)  # Friday
    assert resolve_week("this", TZ, today) == "2026-W43"
    assert resolve_week("next", TZ, today) == "2026-W44"
    assert resolve_week("last", TZ, today) == "2026-W42"
    assert resolve_week("2027-w01", TZ, today) == "2027-W01"


def test_week_dates_is_mon_to_sun():
    days = week_dates("2026-W44")
    assert len(days) == 7
    assert days[0].weekday() == 0 and days[-1].weekday() == 6


def test_bad_week_rejected():
    with pytest.raises(ValueError):
        resolve_week("tomorrow", TZ, date(2026, 1, 1))
    with pytest.raises(ValueError):
        week_start("2026-W60")
