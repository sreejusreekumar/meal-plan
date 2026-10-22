from mealplan.models import Catalogue, DayPlan, Household, Plan, Recipe
from mealplan.shopping import fmt_qty, round_up, shopping_list, to_markdown

CAT = Catalogue.model_validate(
    {
        "items": [
            {"item": "eggs", "unit": "pc", "aisle": "dairy", "packSize": 12},
            {"item": "tomato", "unit": "pc", "aisle": "produce"},
            {"item": "matta rice", "unit": "g", "aisle": "grains", "packSize": 100},
            {"item": "salt", "unit": "tsp", "aisle": "pantry", "staple": True},
        ]
    }
)


def rec(rid, slot, ingredients, name=None):
    return Recipe.model_validate(
        {
            "id": rid,
            "name": name or rid,
            "slot": [slot],
            "cuisine": "t",
            "protein": "egg",
            "nutrition": {"kcal": 400},
            "components": ["x"],
            "ingredients": ingredients,
        }
    )


def two_person_household() -> Household:
    return Household.model_validate(
        {
            "referenceKcal": 1550,
            "people": [
                {"name": "A", "age": 40, "targetKcal": [1550, 1550]},
                {"name": "B", "age": 40, "targetKcal": [1550, 1550]},
            ],
        }
    )


def test_round_up_rules():
    assert round_up(13, "pc", 12) == 24
    assert round_up(2.3, "pc", None) == 3
    assert round_up(1.1, "tsp", None) == 1.5
    assert round_up(37, "g", None) == 40
    assert round_up(437, "g", None) == 450
    assert round_up(1437, "g", None) == 1500
    assert round_up(190, "g", 100) == 200


def test_fmt_qty():
    assert fmt_qty(1500, "g") == "1.5 kg"
    assert fmt_qty(3, "pc") == "3 pcs"
    assert fmt_qty(1, "bunch") == "1 bunch"
    assert fmt_qty(2.5, "tsp") == "2.5 tsp"


def test_merge_scale_round_and_split(household=None):
    hh = two_person_household()  # 2.0 servings
    a = rec(
        "t.breakfast.a",
        "breakfast",
        [{"item": "eggs", "qty": 2}, {"item": "salt", "qty": 0.25}],
        "Omelette",
    )
    b = rec(
        "t.lunch.b",
        "lunch",
        [
            {"item": "eggs", "qty": 1},
            {"item": "tomato", "qty": 1},
            {"item": "matta rice", "qty": 60},
        ],
        "Egg curry",
    )
    plan = Plan(
        week="2026-W44",
        start_date="2026-10-26",
        cuisines=["t"],
        pack_versions={"t": 1},
        seed="s",
        generated_at="now",
        generator="0",
        days=[
            DayPlan(
                date="2026-10-26",
                dow="Mon",
                cuisine="t",
                meals={"breakfast": [a.id], "lunch": [b.id]},
                totals={"kcal": 800},
            ),
        ],
        week_checks={},
        recipes={a.id: a, b.id: b},
    )
    sl = shopping_list(plan, hh, CAT)
    by_item = {line.item: line for line in sl.buy}
    assert set(by_item) == {"eggs", "tomato", "matta rice"}
    assert (
        by_item["eggs"].exact == 6 and by_item["eggs"].qty == 12
    )  # 3 eggs x 2 servings, dozen pack
    assert by_item["eggs"].recipes == ["Omelette", "Egg curry"]
    assert by_item["matta rice"].exact == 120 and by_item["matta rice"].qty == 200
    assert by_item["tomato"].aisle == "produce"
    assert [line.aisle for line in sl.buy] == ["produce", "dairy", "grains"]  # store order
    assert [line.item for line in sl.pantry] == ["salt"]
    md = to_markdown(sl)
    assert "### Produce" in md and "- [ ] eggs — 12 pcs" in md and "## Check pantry" in md


def test_kerala_week_produces_a_list(kerala, household, root_paths):
    """Only meaningful once the Kerala recipes carry ingredients; skipped until then."""
    import pytest

    from mealplan.config import load_catalogue
    from mealplan.generate import generate

    cat = load_catalogue(root_paths)
    if not any(r.ingredients for r in kerala.recipes.values()):
        pytest.skip("Kerala recipes have no ingredients yet")
    plan = generate("2026-W44", [kerala], household, catalogue=cat)
    sl = shopping_list(plan, household, cat)
    assert sl.buy, "a full week must produce something to buy"
    assert all(line.aisle != "other" for line in sl.buy), "every item should resolve to an aisle"
    assert all(not line.staple for line in sl.buy)
