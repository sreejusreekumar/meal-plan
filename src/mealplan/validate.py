"""Health-rule validation: per-day nutrition windows and per-week protein/variety rules.

Everything here is pure: lists of recipes in, list of problem strings out. An empty list
means the day or week passes.
"""

from __future__ import annotations

from mealplan.models import RED_MEAT, SLOTS, Household, Plan, Recipe, WeeklyRules

# plan/household metric key -> Nutrition attribute
METRICS: dict[str, str] = {
    "carbs": "carbs",
    "fibre": "fibre",
    "protein": "protein",
    "satFat": "sat_fat",
    "sugar": "sugar",
}

DayMeals = dict[str, list[Recipe]]


def day_totals(recipes: list[Recipe]) -> dict[str, float]:
    """kcal is always present. Another metric appears only when every recipe provides it,
    so a half-annotated day is never judged on a partial sum."""
    totals: dict[str, float] = {"kcal": sum(r.nutrition.kcal for r in recipes)}
    for key, attr in METRICS.items():
        values = [getattr(r.nutrition, attr) for r in recipes]
        if recipes and all(v is not None for v in values):
            totals[key] = round(sum(values), 1)
    totals["refinedCarbDishes"] = sum(1 for r in recipes if r.refined_carb)
    return totals


def check_day(label: str, totals: dict[str, float], household: Household) -> list[str]:
    problems: list[str] = []
    for metric, (lo, hi) in household.targets_per_reference_day.items():
        value = totals.get(metric)
        if value is None:
            continue
        if lo is not None and value < lo:
            problems.append(f"{label}: {metric} {value:g} is below {lo:g}")
        if hi is not None and value > hi:
            problems.append(f"{label}: {metric} {value:g} is above {hi:g}")
    return problems


def week_checks(days: list[DayMeals]) -> dict[str, int]:
    checks = {
        "fishLunches": 0,
        "chicken": 0,
        "redMeat": 0,
        "legumeDishes": 0,
        "eggMains": 0,
        "treats": 0,
        "vegDinners": 0,
    }
    for day in days:
        for slot in SLOTS:
            recipes = day.get(slot, [])
            if not recipes:
                continue
            proteins = {r.protein for r in recipes}
            mains = [r for r in recipes if r.role == "main"]
            if slot == "lunch" and "fish" in proteins:
                checks["fishLunches"] += 1
            if "chicken" in proteins:
                checks["chicken"] += 1
            if proteins & RED_MEAT:
                checks["redMeat"] += 1
            checks["legumeDishes"] += sum(1 for r in recipes if r.protein == "legume")
            if any(r.protein == "egg" for r in mains):
                checks["eggMains"] += 1
            checks["treats"] += sum(1 for r in recipes if r.treat)
            if slot == "dinner" and all(r.is_vegetarian for r in recipes):
                checks["vegDinners"] += 1
    return checks


def check_week(checks: dict[str, int], rules: WeeklyRules) -> list[str]:
    problems: list[str] = []

    def at_least(key: str, minimum: int) -> None:
        if checks[key] < minimum:
            problems.append(f"week: {key} {checks[key]} is below {minimum}")

    def at_most(key: str, maximum: int) -> None:
        if checks[key] > maximum:
            problems.append(f"week: {key} {checks[key]} is above {maximum}")

    at_least("fishLunches", rules.fish_lunches_min)
    at_most("chicken", rules.chicken_max)
    at_most("redMeat", rules.red_meat_max)
    at_least("legumeDishes", rules.legume_dishes_min)
    at_most("eggMains", rules.egg_mains_max)
    at_most("treats", rules.treats_max)
    at_least("vegDinners", rules.veg_dinners_min)
    return problems


def validate_plan(plan: Plan, household: Household) -> list[str]:
    """Re-derive every check from the plan's own recipe snapshot."""
    problems: list[str] = []
    days: list[DayMeals] = []
    used: dict[str, str] = {}
    for day in plan.days:
        meals: DayMeals = {}
        for slot in SLOTS:
            ids = day.meals.get(slot, [])
            missing = [rid for rid in ids if rid not in plan.recipes]
            if missing:
                problems.append(f"{day.date}: recipes missing from snapshot: {missing}")
                continue
            meals[slot] = [plan.recipes[rid] for rid in ids]
            for r in meals[slot]:
                if r.role == "main" and r.id in used:
                    problems.append(f"{day.date}: {r.id} already used on {used[r.id]}")
                used.setdefault(r.id, day.date)
        days.append(meals)
        recipes = [r for rs in meals.values() for r in rs]
        totals = day_totals(recipes)
        if abs(totals["kcal"] - day.totals.get("kcal", -1)) > 0.5:
            problems.append(f"{day.date}: stored kcal {day.totals.get('kcal')} != {totals['kcal']}")
        problems += check_day(day.date, totals, household)
    checks = week_checks(days)
    if checks != plan.week_checks:
        problems.append(f"week: stored checks {plan.week_checks} != {checks}")
    problems += check_week(checks, household.weekly_rules)
    return problems
