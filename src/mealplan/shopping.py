"""Shopping list: scale a plan's ingredients to the household, merge, round, group by aisle.

Pure: a Plan (with its recipe snapshot), the Household and optionally the Catalogue in; a
ShoppingList out. The same function feeds the CLI files, the web page and the To Do push.
"""

from __future__ import annotations

import math
from collections import OrderedDict

from pydantic import Field

from mealplan.models import AISLES, SLOTS, CamelModel, Catalogue, Household, Ingredient, Plan

COUNT_UNITS = {"pc", "bunch", "sprig"}
SPOON_UNITS = {"tsp", "tbsp"}


class Line(CamelModel):
    item: str
    qty: float
    """Rounded-up quantity to buy (or to have on hand, for pantry lines)."""
    exact: float
    """Scaled total before rounding."""
    unit: str
    aisle: str
    staple: bool = False
    recipes: list[str] = Field(default_factory=list)
    """Recipe names that use this item, in week order, deduplicated."""


class ShoppingList(CamelModel):
    week: str
    servings: float
    buy: list[Line]
    pantry: list[Line]


def round_up(qty: float, unit: str, pack_size: float | None) -> float:
    if pack_size:
        return math.ceil(qty / pack_size - 1e-9) * pack_size
    if unit in COUNT_UNITS:
        return float(math.ceil(qty - 1e-9))
    if unit in SPOON_UNITS:
        return math.ceil(qty * 2 - 1e-9) / 2
    if qty < 100:
        step = 10
    elif qty < 1000:
        step = 50
    else:
        step = 100
    return float(math.ceil(qty / step - 1e-9) * step)


def _resolved(ing: Ingredient, catalogue: Catalogue | None) -> Ingredient:
    if ing.unit and ing.aisle is not None and ing.staple is not None:
        return ing
    if catalogue is not None and ing.item in catalogue.by_name:
        return catalogue.resolve(ing)
    return ing.model_copy(
        update={
            "unit": ing.unit or "pc",
            "aisle": ing.aisle or "other",
            "staple": bool(ing.staple),
        }
    )


def shopping_list(plan: Plan, household: Household, catalogue: Catalogue | None) -> ShoppingList:
    servings = household.servings
    order = catalogue.aisle_order if catalogue else list(AISLES)
    acc: OrderedDict[tuple[str, str], dict] = OrderedDict()
    for day in plan.days:
        for slot in SLOTS:
            for rid in day.meals.get(slot, []):
                recipe = plan.recipes[rid]
                for raw in recipe.ingredients:
                    ing = _resolved(raw, catalogue)
                    key = (ing.item, ing.unit or "pc")
                    entry = acc.setdefault(
                        key,
                        {
                            "item": ing.item,
                            "unit": ing.unit,
                            "aisle": ing.aisle,
                            "staple": ing.staple,
                            "pack_size": ing.pack_size,
                            "exact": 0.0,
                            "recipes": [],
                        },
                    )
                    entry["exact"] += ing.qty * servings
                    if recipe.name not in entry["recipes"]:
                        entry["recipes"].append(recipe.name)

    def rank(e: dict) -> tuple[int, str]:
        aisle = e["aisle"]
        return (order.index(aisle) if aisle in order else len(order), e["item"])

    buy: list[Line] = []
    pantry: list[Line] = []
    for e in sorted(acc.values(), key=rank):
        exact = round(e["exact"], 2)
        line = Line(
            item=e["item"],
            qty=round_up(exact, e["unit"], e["pack_size"]),
            exact=exact,
            unit=e["unit"],
            aisle=e["aisle"],
            staple=e["staple"],
            recipes=e["recipes"],
        )
        (pantry if line.staple else buy).append(line)
    return ShoppingList(week=plan.week, servings=servings, buy=buy, pantry=pantry)


def fmt_qty(qty: float, unit: str) -> str:
    if unit == "g" and qty >= 1000:
        return f"{qty / 1000:g} kg"
    if unit == "ml" and qty >= 1000:
        return f"{qty / 1000:g} L"
    q = f"{qty:g}"
    if unit not in COUNT_UNITS:
        return f"{q} {unit}"
    plural = {"pc": "pcs", "bunch": "bunches", "sprig": "sprigs"}[unit]
    return f"{q} {unit if qty == 1 else plural}"


def to_markdown(sl: ShoppingList) -> str:
    out = [
        f"# Shopping list · {sl.week}",
        "",
        f"Scaled to {sl.servings:g} adult servings per meal.",
        "",
    ]
    out.append("## Buy")
    current = None
    for line in sl.buy:
        if line.aisle != current:
            current = line.aisle
            out += ["", f"### {current.title()}", ""]
        out.append(
            f"- [ ] {line.item} — {fmt_qty(line.qty, line.unit)}  ({', '.join(line.recipes)})"
        )
    if sl.pantry:
        out += ["", "## Check pantry", ""]
        for line in sl.pantry:
            out.append(f"- [ ] {line.item} — about {fmt_qty(line.qty, line.unit)} this week")
    return "\n".join(out) + "\n"
