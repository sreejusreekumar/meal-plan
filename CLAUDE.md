# meal-plan – notes for Claude Code

Python 3.12 project managed with **uv**. Package in `src/mealplan/`; CLI entry point `mealplan`
(Typer). Run anything with `uv run ...`. Design: `SPEC.md`. Decisions: `docs/decisions/` (ADRs).

## Commands
- `uv sync --all-groups` – install
- `uv run pytest -q` – tests (no network, no clock dependence: pass `now=`/`today=`)
- `uv run ruff check . && uv run ruff format .` – lint/format
- `uv run mealplan validate` – config + packs + committed plans
- `uv run mealplan build --check` – is the committed `index.html` fresh? CI runs this.

## Invariants
- **Plans are immutable once committed.** `plans/<week>.json` embeds a snapshot of every recipe
  it uses. Never edit a plan by hand; regenerate with `--force` (and usually a new `--salt`).
- **Determinism.** `generate()` must give the same plan for the same (cuisines, week, pack
  versions, salt). Randomness only through the seeded `random.Random`; never iterate sets or
  dicts in an order-dependent way without sorting.
- **`index.html` is build output.** Change `src/mealplan/web/template.html`, then
  `uv run mealplan build`. Keep the page vanilla HTML/CSS/JS, single file, no framework.
- **Public repo.** No tokens, no personal data beyond names/ages in `config/household.yaml`.
  The Microsoft token cache lives in `~/.config/meal-plan/`.
- **Rules are data.** Health constraints live in `config/household.yaml`; cuisine-specific
  guardrails in `cuisines/<id>/pack.yaml`. Don't hardcode them in Python or JS.
- Recipe quantities are **per adult reference serving**; scaling happens in `shopping.py`.
- Nutrition `carbs` = available carbohydrate (fibre excluded, as on Australian labels); `sugar` = added sugar.
- camelCase in YAML/JSON, snake_case in Python (`CamelModel` handles both).

## Layers
- `models.py` – pydantic models. `packs.py` – load + structural checks. `validate.py` – pure
  health checks. `generate.py` – planner. `build.py` – page + manifest. `cli.py` – Typer only,
  no logic. `integrations/mstodo.py` (phase 3) – Graph client, mirrors shopping-assistant's.

## Conventions
- Bump `pack.yaml: version` when recipe nutrition or ids change; it is part of the seed.
- A new weekly rule needs: `WeeklyRules` field, counting in `validate.week_checks`, enforcement
  or steering in `generate._eligible`/`_score`, a failing test first.
- Tests must not depend on today's date.
