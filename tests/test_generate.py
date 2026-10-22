from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from mealplan.generate import GenerationError, generate, seed_string
from mealplan.models import DOWS, LoadedPack, Pack, Recipe
from mealplan.validate import validate_plan
from mealplan.weeks import is_weekend, week_dates

NOW = datetime(2026, 10, 24, 6, 0, tzinfo=ZoneInfo("Australia/Melbourne"))


def meals_of(plan):
    return [d.meals for d in plan.days]


def test_same_inputs_same_plan(kerala, household):
    a = generate("2026-W44", [kerala], household, now=NOW)
    b = generate("2026-W44", [kerala], household, now=NOW)
    assert meals_of(a) == meals_of(b)
    assert a.seed == seed_string(["kerala"], "2026-W44", {"kerala": kerala.pack.version}, 0)
    assert a.model_dump_json(by_alias=True) == b.model_dump_json(by_alias=True)


def test_salt_and_week_change_the_plan(kerala, household):
    base = generate("2026-W44", [kerala], household, now=NOW)
    assert meals_of(generate("2026-W44", [kerala], household, salt=1, now=NOW)) != meals_of(base)
    assert meals_of(generate("2026-W45", [kerala], household, now=NOW)) != meals_of(base)


@pytest.mark.parametrize("week", ["2026-W44", "2026-W45", "2026-W46", "2027-W02", "2027-W09"])
def test_generated_weeks_obey_the_rules(kerala, household, week):
    plan = generate(week, [kerala], household, now=NOW)
    assert validate_plan(plan, household) == []
    rules = household.weekly_rules
    c = plan.week_checks
    assert c["fishLunches"] >= rules.fish_lunches_min
    assert c["chicken"] <= rules.chicken_max
    assert c["redMeat"] <= rules.red_meat_max
    assert c["treats"] <= rules.treats_max
    assert c["vegDinners"] >= rules.veg_dinners_min
    mains = [rid for d in plan.days for ids in d.meals.values() for rid in ids]
    assert len(mains) == len(set(mains)), "no main repeats within a week"
    for day, d in zip(week_dates(week), plan.days, strict=True):
        recipes = [plan.recipes[r] for ids in d.meals.values() for r in ids]
        if not is_weekend(day):
            assert all(r.effort == "weekday" for r in recipes)
        if DOWS[day.weekday()] in household.packed_lunch_days:
            assert all(plan.recipes[r].packable for r in d.meals["lunch"])
        lo, hi = household.targets_per_reference_day["kcal"]
        assert lo <= d.totals["kcal"] <= hi


def test_history_steers_away_from_recent_recipes(kerala, household):
    first = generate("2026-W44", [kerala], household, now=NOW)
    second = generate("2026-W45", [kerala], household, history=[first], now=NOW)
    used_first = {rid for d in first.days for ids in d.meals.values() for rid in ids}
    used_second = {rid for d in second.days for ids in d.meals.values() for rid in ids}
    # 108 recipes, 28 per week: with history steering, overlap should be small.
    assert len(used_first & used_second) <= 6


def _tiny_pack() -> LoadedPack:
    def rec(slot, i, **kw):
        base = dict(
            id=f"tiny.{slot}.r{i}",
            name=f"{slot} {i}",
            slot=[slot],
            cuisine="tiny",
            nutrition={"kcal": {"breakfast": 370, "lunch": 530, "snack": 120, "dinner": 490}[slot]},
            components=["x"],
        )
        base.update(kw)
        return Recipe.model_validate(base)

    recipes = {}
    for slot in ("breakfast", "snack", "dinner"):
        for i in range(8):
            r = rec(slot, i, protein="legume")
            recipes[r.id] = r
    for i in range(
        8
    ):  # lunches are chicken only and never packable: cannot satisfy fish/packed rules
        r = rec("lunch", i, protein="chicken", packable=False)
        recipes[r.id] = r
    pack = Pack(id="tiny", name="Tiny", version=1)
    return LoadedPack(pack=pack, recipes=recipes)


def test_impossible_pack_fails_loudly(household):
    with pytest.raises(GenerationError) as exc:
        generate("2026-W44", [_tiny_pack()], household, now=NOW)
    assert "lunch" in str(exc.value)
