from mealplan.models import SLOTS
from mealplan.packs import check_pack, list_pack_ids


def test_kerala_pack_loads_and_is_ready(root_paths, kerala):
    assert "kerala" in list_pack_ids(root_paths.cuisines_dir)
    assert check_pack(kerala) == []
    for slot in SLOTS:
        assert len(kerala.candidates(slot, "main")) >= kerala.pack.minimum_recipes[slot]


def test_kerala_recipes_have_kcal_and_components(kerala):
    for r in kerala.recipes.values():
        assert r.nutrition.kcal > 0
        assert r.components
        assert r.cuisine == "kerala"
        if r.protein in ("beef", "pork"):
            assert r.lean


def test_treats_are_weekend_only(kerala):
    treats = [r for r in kerala.recipes.values() if r.treat]
    assert treats, "the Kerala pack should keep its Sunday appam"
    assert all(r.effort == "weekend" for r in treats)
