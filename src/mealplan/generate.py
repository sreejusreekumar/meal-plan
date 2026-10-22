"""Deterministic weekly plan generation.

Same cuisines + week + pack versions + salt -> same plan, always. A seeded PRNG breaks
ties among the best-scoring candidates; everything else is ordered and rule-driven.
"""

from __future__ import annotations

import hashlib
import random
from collections import Counter
from collections.abc import Sequence
from dataclasses import dataclass, field
from datetime import date, datetime
from zoneinfo import ZoneInfo

from mealplan import __version__
from mealplan.models import (
    DOWS,
    RED_MEAT,
    SLOTS,
    Catalogue,
    DayPlan,
    Household,
    LoadedPack,
    Plan,
    Recipe,
)
from mealplan.validate import DayMeals, check_day, check_week, day_totals, week_checks
from mealplan.weeks import dow_short, is_weekend, week_dates, week_start

MAX_ATTEMPTS = 25
TOP_N = 3


class GenerationError(RuntimeError):
    """The packs cannot satisfy the household rules. The message names the rules."""


def seed_string(pack_ids: Sequence[str], week: str, versions: dict[str, int], salt: int) -> str:
    vers = ",".join(f"{pid}={versions[pid]}" for pid in pack_ids)
    return f"{','.join(pack_ids)}:{week}:{vers}:{salt}"


def _seed_int(seed: str) -> int:
    return int(hashlib.sha256(seed.encode("utf-8")).hexdigest(), 16) % (2**62)


@dataclass
class _WeekState:
    household: Household
    history: Counter[str]
    used: set[str] = field(default_factory=set)
    chosen: list[Recipe] = field(default_factory=list)
    counts: Counter[str] = field(default_factory=Counter)
    days: list[DayMeals] = field(default_factory=list)

    @property
    def rules(self):
        return self.household.weekly_rules


def _non_staple_items(r: Recipe, staples: set[str]) -> set[str]:
    return {i.item.lower() for i in r.ingredients if not i.staple and i.item.lower() not in staples}


def _eligible(
    r: Recipe,
    slot: str,
    role: str,
    day: date,
    state: _WeekState,
    remaining_days: int,
) -> bool:
    rules = state.rules
    weekend = is_weekend(day)
    if r.effort == "weekend" and not weekend:
        return False
    if r.treat and state.counts["treats"] >= rules.treats_max:
        return False
    if r.protein == "chicken" and state.counts["chicken"] >= rules.chicken_max:
        return False
    if r.protein in RED_MEAT and (not r.lean or state.counts["redMeat"] >= rules.red_meat_max):
        return False
    if role == "main":
        if r.protein == "egg" and state.counts["eggMains"] >= rules.egg_mains_max:
            return False
        if slot == "lunch":
            packed = DOWS[day.weekday()] in state.household.packed_lunch_days
            if packed and not r.packable:
                return False
            fish_needed = rules.fish_lunches_min - state.counts["fishLunches"]
            if fish_needed >= remaining_days and r.protein != "fish":
                return False
        if slot == "dinner":
            veg_needed = rules.veg_dinners_min - state.counts["vegDinners"]
            if veg_needed >= remaining_days and not r.is_vegetarian:
                return False
    return True


def _score(
    r: Recipe,
    slot: str,
    role: str,
    day: date,
    state: _WeekState,
    today: list[Recipe],
    yesterday: DayMeals | None,
) -> float:
    rules = state.rules
    score = 0.0
    if r.protein != "none":
        if yesterday and any(x.protein == r.protein for x in yesterday.get(slot, [])):
            score -= 2
        if any(x.protein == r.protein for x in today):
            score -= 1
    score -= 3 * state.history.get(r.id, 0)
    if r.family:
        score -= 1.5 * sum(1 for x in state.chosen if x.family == r.family)
        if yesterday and any(x.family == r.family for x in yesterday.get(slot, [])):
            score -= 1.5
    if not is_weekend(day) and r.minutes is not None and r.minutes > 45:
        score -= 1
    if (
        slot == "lunch"
        and r.protein == "fish"
        and state.counts["fishLunches"] < rules.fish_lunches_min
    ):
        score += 1.5
    if r.protein == "legume" and state.counts["legumeDishes"] < rules.legume_dishes_min:
        score += 1
    if slot == "dinner" and r.is_vegetarian and state.counts["vegDinners"] < rules.veg_dinners_min:
        score += 1
    if slot == "lunch" and yesterday and r.leftover_of:
        if any(x.id == r.leftover_of for x in yesterday.get("dinner", [])):
            score += 2
    staples = {s.lower() for s in state.household.pantry_staples}
    mine = _non_staple_items(r, staples)
    if mine:
        shared = sum(len(mine & _non_staple_items(x, staples)) for x in state.chosen)
        score += min(1.0, 0.2 * shared)
    if slot == SLOTS[-1] and role == "main":
        # Last slot of the day: steer every tracked metric into its window, not just kcal.
        totals = day_totals([*today, r])
        for metric, (lo, hi) in state.household.targets_per_reference_day.items():
            value = totals.get(metric)
            if value is None:
                continue
            if lo is not None and value < lo:
                score -= 5 + (lo - value) / max(lo, 1) * 10
            if hi is not None and value > hi:
                score -= 5 + (value - hi) / max(hi, 1) * 10
            if metric == "kcal" and lo is not None and hi is not None:
                score -= abs(value - (lo + hi) / 2) / 50
    return score


def _record(state: _WeekState, slot: str, recipes: list[Recipe]) -> None:
    proteins = {r.protein for r in recipes}
    mains = [r for r in recipes if r.role == "main"]
    if slot == "lunch" and "fish" in proteins:
        state.counts["fishLunches"] += 1
    if "chicken" in proteins:
        state.counts["chicken"] += 1
    if proteins & RED_MEAT:
        state.counts["redMeat"] += 1
    state.counts["legumeDishes"] += sum(1 for r in recipes if r.protein == "legume")
    if any(r.protein == "egg" for r in mains):
        state.counts["eggMains"] += 1
    state.counts["treats"] += sum(1 for r in recipes if r.treat)
    if slot == "dinner" and recipes and all(r.is_vegetarian for r in recipes):
        state.counts["vegDinners"] += 1


def _build_week(
    rng: random.Random,
    dates: list[date],
    packs: Sequence[LoadedPack],
    household: Household,
    history: Counter[str],
) -> tuple[list[DayMeals], list[str], list[dict[str, float]]]:
    state = _WeekState(household=household, history=history)
    problems: list[str] = []
    totals_out: list[dict[str, float]] = []
    for i, day in enumerate(dates):
        pack = packs[i % len(packs)]
        remaining = len(dates) - i
        yesterday = state.days[-1] if state.days else None
        meals: DayMeals = {}
        today: list[Recipe] = []
        for slot in SLOTS:
            comp = pack.pack.slots[slot]
            roles = list(comp.compose) + [r for r in comp.optional if rng.random() < 0.5]
            picked: list[Recipe] = []
            for role in roles:
                cands = [
                    r
                    for r in pack.candidates(slot, role)
                    if r.id not in state.used and _eligible(r, slot, role, day, state, remaining)
                ]
                if not cands:
                    if role in comp.compose:
                        problems.append(f"{day}: no eligible {slot}/{role} in pack {pack.pack.id}")
                    continue
                scored = sorted(
                    cands,
                    key=lambda r: (-_score(r, slot, role, day, state, today, yesterday), r.id),
                )
                choice = rng.choice(scored[:TOP_N])
                picked.append(choice)
                state.used.add(choice.id)
                state.chosen.append(choice)
                today.append(choice)
            meals[slot] = picked
            _record(state, slot, picked)
        state.days.append(meals)
        totals = day_totals(today)
        totals_out.append(totals)
        problems += check_day(str(day), totals, household)
    problems += check_week(week_checks(state.days), household.weekly_rules)
    return state.days, problems, totals_out


def _resolved(r: Recipe, catalogue: Catalogue | None) -> Recipe:
    """Snapshot copy with aisle/staple/packSize filled in, so the plan is self-contained."""
    if catalogue is None or not r.ingredients:
        return r
    return r.model_copy(update={"ingredients": [catalogue.resolve(i) for i in r.ingredients]})


def history_counter(previous: Sequence[Plan]) -> Counter[str]:
    c: Counter[str] = Counter()
    for plan in previous:
        for day in plan.days:
            for ids in day.meals.values():
                c.update(ids)
    return c


def generate(
    week: str,
    packs: Sequence[LoadedPack],
    household: Household,
    salt: int = 0,
    history: Sequence[Plan] = (),
    now: datetime | None = None,
    catalogue: Catalogue | None = None,
) -> Plan:
    if not packs:
        raise GenerationError("no cuisine packs given")
    pack_ids = [p.pack.id for p in packs]
    versions = {p.pack.id: p.pack.version for p in packs}
    seed = seed_string(pack_ids, week, versions, salt)
    base = _seed_int(seed)
    dates = week_dates(week)
    hist = history_counter(history)

    last_problems: list[str] = []
    for attempt in range(MAX_ATTEMPTS):
        rng = random.Random(base + attempt)
        days, problems, totals = _build_week(rng, dates, packs, household, hist)
        if not problems:
            break
        last_problems = problems
    else:
        raise GenerationError(
            f"could not build a valid week for {week} with {', '.join(pack_ids)} after "
            f"{MAX_ATTEMPTS} attempts. Last problems: " + "; ".join(last_problems)
        )

    now = now or datetime.now(ZoneInfo(household.timezone))
    snapshot: dict[str, Recipe] = {}
    day_plans: list[DayPlan] = []
    for i, (day, meals) in enumerate(zip(dates, days, strict=True)):
        ids = {slot: [r.id for r in rs] for slot, rs in meals.items()}
        for rs in meals.values():
            for r in rs:
                snapshot[r.id] = _resolved(r, catalogue)
        day_plans.append(
            DayPlan(
                date=day.isoformat(),
                dow=dow_short(day),
                cuisine=packs[i % len(packs)].pack.id,
                meals=ids,
                totals=totals[i],
            )
        )
    return Plan(
        week=week,
        start_date=week_start(week).isoformat(),
        cuisines=pack_ids,
        pack_versions=versions,
        seed=seed,
        salt=salt,
        generated_at=now.isoformat(timespec="seconds"),
        generator=__version__,
        days=day_plans,
        week_checks=dict(week_checks(days)),
        recipes=dict(sorted(snapshot.items())),
    )
