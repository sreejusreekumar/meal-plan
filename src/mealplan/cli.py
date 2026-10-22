"""`mealplan` command line."""

from __future__ import annotations

from pathlib import Path

import typer
import yaml
from rich.console import Console
from rich.table import Table

from mealplan import build as build_mod
from mealplan.config import load_household, load_rotation, paths
from mealplan.generate import GenerationError, generate
from mealplan.models import SLOTS, Plan, Recipe
from mealplan.packs import (
    PackError,
    check_pack,
    list_pack_ids,
    load_pack,
    load_packs,
    parse_cuisine_arg,
)
from mealplan.validate import validate_plan
from mealplan.weeks import resolve_week, week_start

app = typer.Typer(no_args_is_help=True, help="Deterministic weekly family meal planner.")
todo_app = typer.Typer(help="Microsoft To Do (phase 3).")
app.add_typer(todo_app, name="todo")
console = Console()
err = Console(stderr=True, style="bold red")


def _fail(msg: str, code: int = 1) -> None:
    err.print(msg)
    raise typer.Exit(code)


def _rotation_pick(week: str, rotation: list[str]) -> str:
    if not rotation:
        _fail("no --cuisine given and config/rotation.yaml is empty")
    number = week_start(week).isocalendar()[1]
    return rotation[(number - 1) % len(rotation)]


def _print_week(plan: Plan) -> None:
    table = Table(title=f"{plan.week} · {', '.join(plan.cuisines)} · seed {plan.seed}")
    table.add_column("Day", style="bold")
    for slot in SLOTS:
        table.add_column(slot.title())
    table.add_column("kcal", justify="right")
    for day in plan.days:
        cells = [f"{day.dow} {day.date[5:]}"]
        for slot in SLOTS:
            names = [plan.recipes[rid].name for rid in day.meals.get(slot, [])]
            cells.append("\n".join(names) or "—")
        cells.append(f"{day.totals.get('kcal', 0):g}")
        table.add_row(*cells)
    console.print(table)
    console.print("Week checks:", plan.week_checks)


@app.command()
def plan(
    cuisine: str | None = typer.Option(
        None, "--cuisine", "-c", help="Pack id, or comma list for a mixed week. Default: rotation."
    ),
    week: str = typer.Option("next", "--week", "-w", help="this | next | last | YYYY-Www"),
    salt: int = typer.Option(0, help="Reroll knob; recorded in the plan."),
    force: bool = typer.Option(False, "--force", help="Overwrite an existing plan for that week."),
) -> None:
    """Generate and validate a week, then write plans/<week>.json."""
    p = paths()
    household = load_household(p)
    wk = resolve_week(week, household.timezone)
    out = build_mod.plan_path(p, wk)
    if out.exists() and not force:
        _fail(f"{out} exists. Use --force to replace it (or --salt N for a different week).")
    ids = (
        parse_cuisine_arg(cuisine)
        if cuisine
        else parse_cuisine_arg(_rotation_pick(wk, load_rotation(p)))
    )
    try:
        packs = load_packs(p.cuisines_dir, ids)
    except PackError as exc:
        _fail(str(exc))
    for lp in packs:
        problems = check_pack(lp)
        if problems:
            _fail(f"pack {lp.pack.id} is not ready:\n  " + "\n  ".join(problems))
    history = [pl for pl in build_mod.all_plans(p) if pl.week < wk][-2:]
    try:
        result = generate(wk, packs, household, salt=salt, history=history)
    except GenerationError as exc:
        _fail(str(exc))
    build_mod.save_plan(p, result)
    _print_week(result)
    console.print(f"[green]Wrote {out}[/]. Now run [bold]mealplan build[/] to refresh index.html.")


@app.command()
def show(week: str = typer.Option("this", "--week", "-w")) -> None:
    """Print a generated week."""
    p = paths()
    household = load_household(p)
    wk = resolve_week(week, household.timezone)
    f = build_mod.plan_path(p, wk)
    if not f.exists():
        _fail(f"no plan for {wk} ({f})")
    _print_week(build_mod.load_plan(f))


@app.command()
def validate(
    cuisine: str | None = typer.Option(None, "--cuisine", "-c", help="Only this pack."),
) -> None:
    """Validate household config, cuisine packs and every committed plan."""
    p = paths()
    household = load_household(p)
    console.print(f"household: {len(household.people)} people, {household.servings} servings/meal")
    ids = parse_cuisine_arg(cuisine) if cuisine else list_pack_ids(p.cuisines_dir)
    bad = 0
    for pid in ids:
        try:
            lp = load_pack(p.cuisines_dir, pid)
        except PackError as exc:
            err.print(str(exc))
            bad += 1
            continue
        problems = check_pack(lp)
        status = "[green]ok[/]" if not problems else "[red]" + "; ".join(problems) + "[/]"
        console.print(f"pack {pid} v{lp.pack.version}: {len(lp.recipes)} recipes · {status}")
        bad += bool(problems)
    if not cuisine:
        for pl in build_mod.all_plans(p):
            problems = validate_plan(pl, household)
            status = "[green]ok[/]" if not problems else "[red]" + "; ".join(problems) + "[/]"
            console.print(f"plan {pl.week}: {status}")
            bad += bool(problems)
    if bad:
        raise typer.Exit(1)


@app.command()
def cuisines() -> None:
    """List cuisine packs and their recipe counts."""
    p = paths()
    table = Table("id", "name", "version", *SLOTS, "ready")
    for pid in list_pack_ids(p.cuisines_dir):
        try:
            lp = load_pack(p.cuisines_dir, pid)
        except PackError as exc:
            table.add_row(pid, "?", "?", *["?"] * len(SLOTS), f"[red]{exc}[/]")
            continue
        counts = [str(len(lp.candidates(s, "main"))) for s in SLOTS]
        ready = "[green]yes[/]" if not check_pack(lp) else "[yellow]no[/]"
        table.add_row(pid, lp.pack.name, str(lp.pack.version), *counts, ready)
    console.print(table)


@app.command()
def recipe(recipe_id: str = typer.Argument(..., help="e.g. kerala.lunch.netholi-peera")) -> None:
    """Print a recipe, ingredients scaled to the household."""
    p = paths()
    household = load_household(p)
    found: Recipe | None = None
    for pid in list_pack_ids(p.cuisines_dir):
        if recipe_id.startswith(pid + "."):
            found = load_pack(p.cuisines_dir, pid).recipes.get(recipe_id)
    if found is None:
        for pl in reversed(build_mod.all_plans(p)):
            if recipe_id in pl.recipes:
                found = pl.recipes[recipe_id]
                break
    if found is None:
        _fail(f"no recipe {recipe_id!r}")
    r = found
    console.print(f"[bold]{r.name}[/]  ({r.id})")
    console.print(
        f"{'/'.join(r.slot)} · {r.protein} · {r.spice} · ~{r.nutrition.kcal} kcal per adult"
        + (f" · {r.minutes} min" if r.minutes else "")
    )
    if r.kid_note:
        console.print(f"Kid: {r.kid_note}")
    if r.components:
        console.print("\n[bold]On the plate[/]")
        for c in r.components:
            console.print(f"  • {c}")
    if r.ingredients:
        console.print(f"\n[bold]Ingredients for the household ({household.servings} servings)[/]")
        for ing in r.ingredients:
            console.print(f"  • {ing.item}: {ing.qty * household.servings:g} {ing.unit}")
    else:
        console.print("\n[dim]No ingredient quantities yet (phase 1 authoring).[/]")
    if r.steps:
        console.print("\n[bold]Steps[/]")
        for i, s in enumerate(r.steps, 1):
            console.print(f"  {i}. {s}")
    if r.swaps:
        console.print("\n[bold]Swaps[/]")
        for s in r.swaps:
            console.print(f"  • instead of {s.for_}: {s.use}" + (f" ({s.note})" if s.note else ""))
    if r.swap_note:
        console.print(f"  • {r.swap_note}")


@app.command()
def build(
    check: bool = typer.Option(
        False, "--check", help="Exit 1 if index.html is stale; write nothing."
    ),
) -> None:
    """Regenerate index.html and plans/manifest.json from the committed plans."""
    p = paths()
    if check:
        if build_mod.is_stale(p):
            _fail("index.html or plans/manifest.json is stale: run `mealplan build` and commit.")
        console.print("[green]index.html is up to date[/]")
        return
    _, man = build_mod.build(p)
    console.print(
        f"[green]Wrote {p.index_html}[/] · current {man['current']} · next {man['next']} "
        f"· version {man['version']}"
    )


@app.command("add-cuisine")
def add_cuisine(
    pack_id: str = typer.Argument(..., help="lowercase id, e.g. thai"),
    name: str = typer.Option(None, help="Display name; defaults to the id in Title Case."),
) -> None:
    """Scaffold cuisines/<id>/ with a pack.yaml and one example recipe per slot."""
    p = paths()
    pack_dir = p.cuisines_dir / pack_id
    if pack_dir.exists():
        _fail(f"{pack_dir} already exists")
    (pack_dir / "recipes").mkdir(parents=True)
    display = name or pack_id.replace("-", " ").title()
    pack = {
        "id": pack_id,
        "name": display,
        "version": 1,
        "description": (
            f"{display} recipes. Author with docs/authoring.md, "
            f"then `mealplan validate -c {pack_id}`."
        ),
        "slots": {s: {"compose": ["main"]} for s in SLOTS},
        "minimumRecipes": {"breakfast": 10, "lunch": 10, "snack": 7, "dinner": 10},
        "minimumPackableLunches": 5,
        "slotLabels": {s: s.title() for s in SLOTS},
        "rules": [{"title": "Plate order", "text": "Vegetables first, protein next, grains last."}],
    }
    (pack_dir / "pack.yaml").write_text(yaml.safe_dump(pack, sort_keys=False, allow_unicode=True))
    for s in SLOTS:
        rid = f"{pack_id}.{s}.example"
        example = {
            "id": rid,
            "name": f"Example {s}",
            "slot": [s],
            "role": "main",
            "cuisine": pack_id,
            "protein": "legume",
            "spice": "medium",
            "packable": s == "lunch",
            "effort": "weekday",
            "nutrition": {"kcal": {"breakfast": 370, "lunch": 530, "snack": 120, "dinner": 490}[s]},
            "components": ["Replace me"],
            "ingredients": [
                {"item": "example ingredient", "qty": 100, "unit": "g", "aisle": "produce"}
            ],
            "steps": ["Replace me"],
        }
        (pack_dir / "recipes" / f"{rid}.yaml").write_text(
            yaml.safe_dump(example, sort_keys=False, allow_unicode=True)
        )
    console.print(
        f"[green]Scaffolded {pack_dir}[/]. Add recipes, then `mealplan validate -c {pack_id}`."
    )


@todo_app.command("login")
def todo_login() -> None:
    """Sign in to Microsoft once (phase 3)."""
    _fail("Microsoft To Do integration arrives in phase 3.")


def main() -> None:  # pragma: no cover
    app()


if __name__ == "__main__":  # pragma: no cover
    main()


__all__ = ["app", "main", "Path"]
