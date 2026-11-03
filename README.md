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

## Generating a week and refreshing the deployed page

The site (https://sreejusreekumar.github.io/meal-plan/) is a static page built from the files in
this repo. GitHub computes nothing: whatever `index.html` is on `main` is what every device shows.
Publishing a week is therefore four steps.

```
uv run mealplan plan --week next            # 1. plans/<week>.json (cuisine from config/rotation.yaml, or --cuisine thai)
uv run mealplan shop --week next --todo     # 2. shopping/<week>.md + .json, and the Weekly Basket list in To Do
uv run mealplan build                       # 3. bakes current + next week into index.html, writes plans/manifest.json
git add -A && git commit -m "Plan 2026-W45" && git push   # 4. GitHub Pages redeploys within about a minute
```

Or all of 1–3 in one go: `uv run mealplan weekly --week next --todo`, then commit and push.

**How the kitchen tablet refreshes.** The open page fetches `plans/manifest.json` every 15 minutes,
and whenever it is brought back to the foreground. The manifest carries a version hash of all plan
files; when it differs from the hash baked into the page, the page reloads itself. So after a push
the new week appears on its own within 15 minutes, with no one touching the device. To see it
immediately, pull the page down to refresh or press reload.

**Checks before you push.** `uv run mealplan validate` checks config, packs and every plan;
`uv run mealplan build --check` fails if `index.html` is older than the plans (CI runs the same
check, so a forgotten build fails the build on GitHub rather than silently publishing a stale page).

**Changing your mind about a week.** `uv run mealplan plan --week next --salt 1 --force` rerolls it;
the salt is recorded in the plan file, so the result is still reproducible. Then shop, build, commit,
push again: the To Do push replaces the planner's tasks, and the page reloads.

**If the page does not update.** In order: `git status` (did the plan and `index.html` get committed?),
`git log origin/main -1` (did the push land?), the repo's Actions tab (did the Pages deployment run?),
then a hard reload on the device. The footer of the page shows the plan week and the version hash,
which should match `plans/manifest.json` on `main`.

**On the page.** The **Shopping** tab shows the list with tick boxes (per device) and a copy button.
Tap any meal card for the recipe: ingredients scaled to the household, method, swaps. Deep links:
`#shopping` opens the list, `#day-2026-10-19` opens a day, `#recipe-lunch` opens the selected day's
lunch recipe. Signature dishes of a cuisine carry a badge and a one-line note.

## Saturday automation

Two jobs, no secrets in GitHub (ADR 0004):

- **GitHub Actions** (`.github/workflows/weekly.yml`): Saturday 06:00 Melbourne, runs
  `mealplan weekly --week next`, validates, and commits `plans/`, `shopping/` and `index.html`.
  Pages serves the commit, and the kitchen tablet reloads itself within 15 minutes.
  Run it by hand from the repo's **Actions** tab ("Run workflow", with week/cuisine/salt/force) or
  with `gh workflow run weekly.yml -f cuisine=thai -f salt=1 -f force=true`.
- **This Mac** (`scripts/weekly-todo.sh` via launchd, Saturday 06:30): `git pull`, then
  `mealplan todo push --week next`. Install or reinstall with `./scripts/install-launchd.sh`;
  log at `~/Library/Logs/meal-plan.log`; run it now with
  `launchctl kickstart -k gui/$(id -u)/com.mealplan.todo`.

The same routine by hand: `uv run mealplan weekly --week next --todo`, then commit and push.

## Microsoft To Do

The shopping list is pushed to one dedicated To Do list, **Weekly Basket** (name in
`config/household.yaml`), created on the first push. One task per item in store-walk order, with
the recipes in the note; pantry staples as one "Check pantry" task with sub-items. Re-running for
the same week replaces the planner's tasks; anything you typed by hand is left alone.

One-time setup:

```
cp .env.example .env            # then fill MEALPLAN_MS_CLIENT_ID (same app as shopping-assistant)
uv run mealplan todo login      # device code: open the link, enter the code, done
uv run mealplan todo status
```

Weekly:

```
uv run mealplan shop --week next --todo     # or: uv run mealplan todo push --week next
```

The token cache lives in `~/.config/meal-plan/ms_token_cache.json`, never in the repo.

## Cuisines: where they live and how to pick one

Each cuisine is a **pack**: a folder under `cuisines/` holding `pack.yaml` (name, slot labels,
the "Every day" guardrails shown on the page) and `recipes/<id>.yaml`, one file per dish.
`uv run mealplan cuisines` lists the packs you have and whether each is ready. Ten packs today:
Kerala, North Indian, Sri Lankan, Thai, Mediterranean, Japanese, Middle Eastern, Korean, Mexican,
Vietnamese; the rotation cycles through them by ISO week number. Every dish is listed in
[docs/packs.md](docs/packs.md).

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
uv run mealplan trial -c thai        # can it build 8 weeks inside the health windows?
```

A pack is usable once it has at least 10 breakfast, 10 lunch, 7 snack and 10 dinner mains, with
5 or more packable lunches. The validator says exactly what is missing.

## Commands

| Command | Purpose |
|---|---|
| `mealplan plan -c <id[,id]> -w <this\|next\|YYYY-Www> [--salt N] [--force]` | Generate and validate a week |
| `mealplan show -w <week>` | Print a week |
| `mealplan shop -w <week> [--todo]` | Write the shopping list for a week |
| `mealplan todo login` / `status` / `push -w <week>` | Microsoft To Do sign-in, check, push |
| `mealplan weekly [-w <week>] [-c <id>] [--salt N] [--force] [--todo]` | plan (if missing) + shop + build |
| `mealplan recipe <id>` | Print a recipe scaled to the household |
| `mealplan build [--check]` | Regenerate `index.html`; `--check` fails if it is stale |
| `mealplan validate [-c <id>]` | Validate config, packs and committed plans |
| `mealplan cuisines` | List packs and recipe counts |
| `mealplan trial -c <id> [--weeks N]` | Dry-run a pack over N weeks; nothing written |
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
