from mealplan.models import Recipe, WeeklyRules
from mealplan.validate import check_day, check_week, day_totals, week_checks


def rec(rid, slot, protein, kcal, **kw):
    base = dict(
        id=rid,
        name=rid,
        slot=[slot],
        cuisine="t",
        protein=protein,
        nutrition={"kcal": kcal},
        components=["x"],
    )
    base.update(kw)
    return Recipe.model_validate(base)


def test_day_totals_only_sums_metrics_everyone_provides():
    a = rec("t.breakfast.a", "breakfast", "egg", 300, nutrition={"kcal": 300, "fibre": 5})
    b = rec("t.lunch.b", "lunch", "fish", 500)
    t = day_totals([a, b])
    assert t["kcal"] == 800
    assert "fibre" not in t
    assert t["refinedCarbDishes"] == 0


def test_check_day_flags_kcal_window(household):
    assert check_day("d", {"kcal": 1200}, household) == ["d: kcal 1200 is below 1450"]
    assert check_day("d", {"kcal": 1700}, household) == ["d: kcal 1700 is above 1650"]
    assert check_day("d", {"kcal": 1500}, household) == []


def test_week_checks_and_rules():
    chicken = rec("t.dinner.c", "dinner", "chicken", 490)
    fish = rec("t.lunch.f", "lunch", "fish", 530)
    dal = rec("t.dinner.d", "dinner", "legume", 480)
    appam = rec("t.breakfast.a", "breakfast", "chicken", 380, treat=True)
    days = [
        {"lunch": [fish], "dinner": [chicken], "breakfast": [appam]},
        {"lunch": [fish], "dinner": [chicken]},
        {"lunch": [fish], "dinner": [chicken]},
        {"lunch": [fish], "dinner": [chicken]},
        {"dinner": [dal]},
    ]
    c = week_checks(days)
    assert c["fishLunches"] == 4
    assert c["chicken"] == 5
    assert c["treats"] == 1
    assert c["vegDinners"] == 1
    assert c["legumeDishes"] == 1
    problems = check_week(c, WeeklyRules())
    assert "week: chicken 5 is above 3" in problems
    assert "week: vegDinners 1 is below 2" in problems
    assert "week: legumeDishes 1 is below 3" in problems
    assert not any("fishLunches" in p for p in problems)


def test_signature_dishes_are_counted_and_required():
    sig = rec("t.lunch.s", "lunch", "fish", 530, signature=True, based_on="A famous dish.")
    plain = rec("t.dinner.p", "dinner", "legume", 480)
    c = week_checks([{"lunch": [sig], "dinner": [plain]}, {"lunch": [sig]}])
    assert c["signatureDishes"] == 2
    problems = check_week(
        c,
        WeeklyRules(
            signature_dishes_min=3, fish_lunches_min=0, legume_dishes_min=0, veg_dinners_min=0
        ),
    )
    assert "week: signatureDishes 2 is below 3" in problems
