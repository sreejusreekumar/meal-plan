# Family Meal Plan

Deterministic weekly meal planner for a family of four with a pre-diabetic, borderline-LDL
profile. Cuisine packs in → a validated week → shopping list → a static page on GitHub Pages
(https://sreejusreekumar.github.io/meal-plan/) that the kitchen tablet refreshes itself.

The full design is in [SPEC.md](SPEC.md). Decisions are in `docs/decisions/`.

## Setup

```
uv sync --all-groups
uv run mealplan --help
```

Python 3.12 managed by [uv](https://docs.astral.sh/uv/). No other runtime is needed; the page is
plain HTML/CSS/JS with no build tooling.

## Weekly runbook (by hand)

```
uv run mealplan plan --cuisine kerala --week next      # or omit --cuisine to follow config/rotation.yaml
uv run mealplan show --week next
uv run mealplan build                                  # regenerates index.html + plans/manifest.json
git add -A && git commit -m "Plan 2026-W45 (Kerala)" && git push
```

Don't like the week? `mealplan plan --week next --salt 1 --force`. The salt is recorded in the plan
file, so the result is still reproducible.

```
uv run mealplan shop --week next                        # shopping/<week>.md + .json, grouped by aisle
```

The page's **Shopping** tab shows the same list with tick boxes (per device) and a copy button.
Tap any meal card on the page for the recipe: ingredients scaled to the household, method, swaps.
Microsoft To Do push (`--todo`, into a dedicated "Weekly Basket" list) arrives in phase 3;
Saturday automation in phase 4.

## Cuisines: where they live and how to pick one

Each cuisine is a **pack**: a folder under `cuisines/` holding `pack.yaml` (name, slot labels,
the "Every day" guardrails shown on the page) and `recipes/<id>.yaml`, one file per dish.
`uv run mealplan cuisines` lists the packs you have and whether each is ready. Only Kerala
exists today.

Pick the cuisine for a week in one of two ways:

1. **By hand.** `--cuisine` takes a pack id, or a comma list for a mixed week where the days
   alternate between packs:

   ```
   uv run mealplan plan --cuisine thai --week next
   uv run mealplan plan --cuisine kerala,thai --week next
   ```

2. **By rotation.** Omit `--cuisine` and the planner reads `config/rotation.yaml`, cycling through
   the list by ISO week number. This is what the Saturday automation will use:

   ```yaml
   rotation:
     - kerala
     - north-indian
     - thai
   ```

To add a country, scaffold it and then write the recipes following
[docs/authoring.md](docs/authoring.md), which includes a prompt for drafting a pack with Claude Code:

```
uv run mealplan add-cuisine thai
uv run mealplan validate -c thai
```

A pack is usable once it has at least 10 breakfast, 10 lunch, 7 snack and 10 dinner mains, with
5 or more packable lunches. The validator says exactly what is missing.

## Commands

| Command | Purpose |
|---|---|
| `mealplan plan -c <id[,id]> -w <this\|next\|YYYY-Www> [--salt N] [--force]` | Generate and validate a week |
| `mealplan show -w <week>` | Print a week |
| `mealplan shop -w <week> [--todo]` | Write the shopping list for a week |
| `mealplan recipe <id>` | Print a recipe scaled to the household |
| `mealplan build [--check]` | Regenerate `index.html`; `--check` fails if it is stale |
| `mealplan validate [-c <id>]` | Validate config, packs and committed plans |
| `mealplan cuisines` | List packs and recipe counts |
| `mealplan add-cuisine <id>` | Scaffold a new pack |

## Layout

- `config/household.yaml` — people, energy targets, weekly rules, To Do list name.
- `config/ingredients.yaml` — the ingredient catalogue: canonical names, units, aisles, staples, pack sizes. Every recipe ingredient must use one of these names.
- `cuisines/<id>/pack.yaml` + `recipes/*.yaml` — one recipe per file, quantities per adult serving.
- `plans/<week>.json` — generated weeks with embedded recipe snapshots. Committed, never edited.
- `src/mealplan/` — the Python package. `web/template.html` is the page; `__PLAN_DATA__` is
  replaced by the inlined JSON at build time.
- `index.html` — build output served by GitHub Pages. CI fails if it is stale.

## Health rules

Defaults encode a pre-diabetic, borderline-LDL/TG profile: whole grains only, fish ≥ 3 lunches a
week, chicken ≤ 3, lean red meat ≤ 1, legumes ≥ 3 dishes, one treat, per-day kcal window per adult
portion. They are data in `config/household.yaml`, not medical advice; tune them with your doctor.
