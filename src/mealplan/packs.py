"""Load cuisine packs from cuisines/<id>/ and check them for structural problems."""

from __future__ import annotations

from pathlib import Path

from pydantic import ValidationError

from mealplan.config import load_yaml
from mealplan.models import SLOTS, Catalogue, LoadedPack, Pack, Recipe


class PackError(ValueError):
    pass


def list_pack_ids(cuisines_dir: Path) -> list[str]:
    if not cuisines_dir.exists():
        return []
    return sorted(p.parent.name for p in cuisines_dir.glob("*/pack.yaml"))


def load_pack(cuisines_dir: Path, pack_id: str) -> LoadedPack:
    pack_dir = cuisines_dir / pack_id
    pack_file = pack_dir / "pack.yaml"
    if not pack_file.exists():
        have = ", ".join(list_pack_ids(cuisines_dir)) or "none"
        raise PackError(f"no cuisine pack {pack_id!r} (have: {have})")
    try:
        pack = Pack.model_validate(load_yaml(pack_file))
    except ValidationError as exc:
        raise PackError(f"{pack_file}: {exc}") from exc
    if pack.id != pack_id:
        raise PackError(f"{pack_file}: id {pack.id!r} does not match folder {pack_id!r}")

    recipes: dict[str, Recipe] = {}
    problems: list[str] = []
    for rf in sorted((pack_dir / "recipes").glob("*.yaml")):
        try:
            recipe = Recipe.model_validate(load_yaml(rf))
        except (ValidationError, ValueError) as exc:
            problems.append(f"{rf.name}: {exc}")
            continue
        if recipe.cuisine != pack.id:
            problems.append(f"{rf.name}: cuisine {recipe.cuisine!r} != pack {pack.id!r}")
        if recipe.id in recipes:
            problems.append(f"{rf.name}: duplicate id {recipe.id}")
        if rf.stem != recipe.id:
            problems.append(f"{rf.name}: file name should be {recipe.id}.yaml")
        recipes[recipe.id] = recipe
    if problems:
        raise PackError(f"pack {pack_id}: " + "; ".join(problems))
    return LoadedPack(pack=pack, recipes=recipes)


def load_packs(cuisines_dir: Path, ids: list[str]) -> list[LoadedPack]:
    return [load_pack(cuisines_dir, i) for i in ids]


def check_pack(lp: LoadedPack, catalogue: Catalogue | None = None) -> list[str]:
    """Problems that make a pack unusable for a full week. Empty list means fine."""
    out: list[str] = []
    for slot in SLOTS:
        comp = lp.pack.slots.get(slot)
        if comp is None:
            out.append(f"slot {slot} has no composition")
            continue
        for role in comp.compose:
            have = len(lp.candidates(slot, role))
            need = lp.pack.minimum_recipes.get(slot, 0) if role == "main" else 1
            if have < need:
                out.append(f"{slot}/{role}: {have} recipes, need at least {need}")
    packable = [r for r in lp.candidates("lunch", "main") if r.packable]
    if len(packable) < lp.pack.minimum_packable_lunches:
        out.append(
            f"lunch: {len(packable)} packable mains, need {lp.pack.minimum_packable_lunches}"
        )
    if catalogue is not None:
        for r in lp.recipes.values():
            out += catalogue.problems(r)
    return out


def parse_cuisine_arg(arg: str) -> list[str]:
    ids = [s.strip() for s in arg.split(",") if s.strip()]
    if not ids:
        raise PackError("no cuisine given")
    return ids
