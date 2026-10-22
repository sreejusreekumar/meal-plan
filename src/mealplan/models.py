"""Pydantic models for recipes, cuisine packs, household config and generated plans.

YAML/JSON keys are camelCase (what humans and the web page see); Python attributes are
snake_case. Every model accepts both spellings on input and emits camelCase on output.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

SLOTS: tuple[str, ...] = ("breakfast", "lunch", "snack", "dinner")
ROLES: tuple[str, ...] = ("main", "side", "carb", "drink", "treat")
PROTEINS: tuple[str, ...] = ("fish", "chicken", "beef", "pork", "egg", "legume", "dairy", "none")
RED_MEAT: frozenset[str] = frozenset({"beef", "pork"})
NON_VEG: frozenset[str] = frozenset({"fish", "chicken", "beef", "pork"})
AISLES: tuple[str, ...] = (
    "produce",
    "fish",
    "meat",
    "dairy",
    "grains",
    "pantry",
    "spices",
    "frozen",
    "other",
)
DOWS: tuple[str, ...] = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")

Slot = Literal["breakfast", "lunch", "snack", "dinner"]
Role = Literal["main", "side", "carb", "drink", "treat"]
Protein = Literal["fish", "chicken", "beef", "pork", "egg", "legume", "dairy", "none"]
Spice = Literal["mild", "medium", "hot"]
Effort = Literal["weekday", "weekend"]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel, populate_by_name=True, extra="forbid", str_strip_whitespace=True
    )

    def dump(self) -> dict:
        """camelCase dict with defaults omitted where they are None."""
        return self.model_dump(by_alias=True, exclude_none=True)


# --------------------------------------------------------------------------- recipes


class Nutrition(CamelModel):
    """Per adult reference serving. Only kcal is mandatory; the validator checks the other
    metrics only when every recipe in a day provides them."""

    kcal: int = Field(ge=0)
    carbs: float | None = Field(default=None, ge=0)
    fibre: float | None = Field(default=None, ge=0)
    protein: float | None = Field(default=None, ge=0)
    sat_fat: float | None = Field(default=None, ge=0)
    sugar: float | None = Field(default=None, ge=0)


class Ingredient(CamelModel):
    item: str
    qty: float = Field(gt=0)
    unit: str
    aisle: Literal[
        "produce", "fish", "meat", "dairy", "grains", "pantry", "spices", "frozen", "other"
    ] = "other"
    staple: bool = False
    pack_size: float | None = Field(default=None, gt=0)


class Swap(CamelModel):
    for_: str = Field(alias="for")
    use: str
    note: str | None = None


class Recipe(CamelModel):
    id: str = Field(pattern=r"^[a-z0-9-]+\.(breakfast|lunch|snack|dinner|any)\.[a-z0-9-]+$")
    name: str
    slot: list[Slot] = Field(min_length=1)
    role: Role = "main"
    cuisine: str
    protein: Protein = "none"
    lean: bool = False
    tags: list[str] = Field(default_factory=list)
    spice: Spice = "medium"
    kid_note: str | None = None
    packable: bool = False
    prep_minutes: int | None = Field(default=None, ge=0)
    cook_minutes: int | None = Field(default=None, ge=0)
    effort: Effort = "weekday"
    treat: bool = False
    refined_carb: bool = False
    leftover_of: str | None = None
    family: str | None = None
    """Variety key finer than protein: the fish (mathi, ayala...) or the dish form (puttu,
    dosa, omelette). The planner avoids repeating a family within a week."""
    nutrition: Nutrition
    components: list[str] = Field(default_factory=list)
    """What is on the plate, one line each, as shown on the page. A line starting with
    'Primary: ' is the dish the plate is built around."""
    ingredients: list[Ingredient] = Field(default_factory=list)
    steps: list[str] = Field(default_factory=list)
    swaps: list[Swap] = Field(default_factory=list)
    swap_note: str | None = None
    source: str | None = None

    @model_validator(mode="after")
    def _rules(self) -> Recipe:
        if self.protein in RED_MEAT and not self.lean:
            raise ValueError(f"{self.id}: red meat recipes must be tagged lean: true")
        if self.role == "treat":
            self.treat = True
        if not self.components and not self.ingredients:
            raise ValueError(f"{self.id}: needs components or ingredients")
        return self

    @property
    def is_vegetarian(self) -> bool:
        return self.protein not in NON_VEG

    @property
    def minutes(self) -> int | None:
        if self.prep_minutes is None and self.cook_minutes is None:
            return None
        return (self.prep_minutes or 0) + (self.cook_minutes or 0)


class SlotComposition(CamelModel):
    compose: list[Role] = Field(default_factory=lambda: ["main"])
    optional: list[Role] = Field(default_factory=list)


class Pack(CamelModel):
    id: str = Field(pattern=r"^[a-z0-9-]+$")
    name: str
    version: int = Field(ge=1)
    description: str | None = None
    slots: dict[Slot, SlotComposition] = Field(
        default_factory=lambda: {s: SlotComposition() for s in SLOTS}
    )
    minimum_recipes: dict[Slot, int] = Field(
        default_factory=lambda: {"breakfast": 10, "lunch": 10, "snack": 7, "dinner": 10}
    )
    minimum_packable_lunches: int = 5
    slot_labels: dict[Slot, str] = Field(
        default_factory=lambda: {
            "breakfast": "Breakfast",
            "lunch": "Lunch",
            "snack": "Snack",
            "dinner": "Dinner",
        }
    )
    rules: list[dict[str, str]] = Field(default_factory=list)
    """Cuisine-specific guardrails shown on the page: [{title, text}, ...]."""


class LoadedPack(BaseModel):
    """A pack plus its recipes, keyed by id."""

    model_config = ConfigDict(arbitrary_types_allowed=True)
    pack: Pack
    recipes: dict[str, Recipe]

    def candidates(self, slot: str, role: str) -> list[Recipe]:
        return sorted(
            (r for r in self.recipes.values() if slot in r.slot and r.role == role),
            key=lambda r: r.id,
        )


# --------------------------------------------------------------------------- household


class Person(CamelModel):
    name: str
    age: int = Field(ge=1)
    target_kcal: tuple[int, int]
    spice: Spice = "medium"

    def factor(self, reference_kcal: int) -> float:
        lo, hi = self.target_kcal
        return round(((lo + hi) / 2) / reference_kcal, 2)


Window = tuple[float | None, float | None]


class WeeklyRules(CamelModel):
    fish_lunches_min: int = 3
    chicken_max: int = 3
    red_meat_max: int = 1
    legume_dishes_min: int = 3
    egg_mains_max: int = 5
    treats_max: int = 1
    veg_dinners_min: int = 2


class TodoConfig(CamelModel):
    mode: Literal["lists-by-aisle", "single-list"] = "lists-by-aisle"
    lists: dict[str, str] = Field(default_factory=lambda: {"default": "Groceries"})


class Household(CamelModel):
    timezone: str = "Australia/Melbourne"
    week_starts: Literal["monday"] = "monday"
    shopping_day: str = "saturday"
    reference_kcal: int = 1550
    people: list[Person]
    packed_lunch_days: list[str] = Field(
        default_factory=lambda: ["mon", "tue", "wed", "thu", "fri"]
    )
    targets_per_reference_day: dict[str, Window] = Field(
        default_factory=lambda: {
            "kcal": (1450, 1650),
            "carbs": (None, 170),
            "fibre": (25, None),
            "protein": (70, None),
            "satFat": (None, 15),
            "sugar": (None, 0),
            "refinedCarbDishes": (None, 1),
        }
    )
    weekly_rules: WeeklyRules = Field(default_factory=WeeklyRules)
    pantry_staples: list[str] = Field(default_factory=list)
    todo: TodoConfig = Field(default_factory=TodoConfig)

    @property
    def servings(self) -> float:
        """Total adult-reference servings the household eats per meal."""
        return round(sum(p.factor(self.reference_kcal) for p in self.people), 2)

    @model_validator(mode="after")
    def _check(self) -> Household:
        bad = [d for d in self.packed_lunch_days if d not in DOWS]
        if bad:
            raise ValueError(f"packedLunchDays has unknown day names: {bad}")
        return self


# --------------------------------------------------------------------------- plans


class DayPlan(CamelModel):
    date: str
    dow: str
    cuisine: str
    meals: dict[Slot, list[str]]
    totals: dict[str, float]


class Plan(CamelModel):
    week: str
    start_date: str
    cuisines: list[str]
    pack_versions: dict[str, int]
    seed: str
    salt: int = 0
    generated_at: str
    generator: str
    days: list[DayPlan]
    week_checks: dict[str, int]
    recipes: dict[str, Recipe]
    """Snapshot of every recipe the week references, so the plan is self-contained."""

    def recipes_for(self, day: DayPlan, slot: str) -> list[Recipe]:
        return [self.recipes[rid] for rid in day.meals[slot]]
