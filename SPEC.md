# Family Meal Planner — Specification

Status: v0.8 (2026-10-23). Phases 0 to 5 are implemented: ten cuisine packs (section 15). All open
questions were settled in review 3 (section 16); section 17 is empty.

## 1. Goal

A repeatable, deterministic, data-driven weekly meal planner for a family of four
that:

1. Lets you choose a cuisine (or add a new one) and generates all meals
   (breakfast, lunch, snack, dinner) for a Monday–Sunday week.
2. Respects the household's health constraints (pre-diabetic, borderline LDL and
   triglycerides) by construction, not by hope.
3. Shows the recipe for any meal on demand, scaled to the household.
4. Produces the week's shopping list, grouped by aisle, and pushes it to
   Microsoft To Do, where the existing shopping-assistant picks it up for price
   comparison.
5. Regenerates `index.html` and publishes it via GitHub Pages so every device
   that has the page open (kitchen tablet, phones) shows the current week.
6. Runs itself every Saturday by default, and can be run by hand at any time.

## 2. Current state

- One file, `index.html` (~500 lines): a hardcoded 28-day Kerala plan as a JS
  array, a kitchen-display UI (today first, big touch targets, light/dark), and
  the plan start date held in `localStorage`.
- Hosted on GitHub Pages from the root of `main`:
  https://sreejusreekumar.github.io/meal-plan/
- Repo is **public**. Nothing personal beyond the menu, and no secrets, may be
  committed.
- Sibling project `~/Projects/shopping-assistant` (Python 3.12, uv, Typer,
  MSAL) already holds a Microsoft app registration for a personal account,
  a device-code login, a token cache, and a scheduled sync that pulls the To Do
  lists "Groceries", "Meat & Fish" and "Vegetables & Fruits" into its price
  comparison. Its sync is read-only; it never writes to Graph.

The existing UI and the Kerala content are kept. The 28 hardcoded days become
the seed of the Kerala recipe pack.

## 3. Household and health rules

### 3.1 Household

Ages 47, 41, 14 and 8. Portions are driven by a per-person energy target, not a
flat adult/child split. The reference portion in every recipe is one "adult
serving" (~1550 kcal/day across the four slots). Each person's factor is
`targetKcal / referenceKcal`, and the shopping list scales by the sum of factors.

| Person | Age | Daily target (default) | Factor | Notes |
|---|---|---|---|---|
| Adult A | 47 | 1600–1800 kcal | 1.1 | Pre-diabetic profile applies |
| Adult B | 41 | 1600–1800 kcal | 1.1 | Pre-diabetic profile applies |
| Teen    | 14 | 2000–2400 kcal | 1.4 | Growing; extra energy comes from the carb role (more rice/roti) and snacks, not from doubling the curry |
| Child   |  8 | 1400–1600 kcal | 0.95 | Spice held back per `kidNote`; same dishes |

Defaults are estimates that ignore sex and activity; they live in
`config/household.yaml` and should be tuned with a doctor or dietitian. The
tool is not medical advice. Household scale ≈ 4.55 adult servings.

Spice: household default is **medium**. Every recipe carries a `spice` level and
a `kidNote` where relevant ("hold the green chilli for one portion").

Lunches are **both** eaten at home and packed (work and school). Lunch recipes
carry `packable: true|false`; on weekdays the generator requires a packable lunch
main and favours dinner-makes-tomorrow's-lunch pairings (section 7).

### 3.2 Health principles encoded as data

- Low glycaemic load: whole grains only (matta/brown rice measured, whole-wheat
  roti, oats, millets), no sugar-sweetened drinks, no added sugar in snacks.
- Fibre first: every lunch and dinner has at least one vegetable dish.
- Protein rotation: fish ≥ 3 lunches/week, chicken ≤ 3/week, **lean red meat
  (beef/pork) allowed, ≤ 1/week and only recipes tagged `lean`**, legumes ≥ 3
  dishes/week, egg-based mains capped per week.
- Fats: saturated fat capped per day, so coconut milk and coconut oil are
  measured, not free; prefer olive/rice-bran/mustard oil; nuts and seeds as
  snacks.
- One "treat" slot per week (e.g. Sunday appam), tagged so the validator counts it.
- Signature dishes: each pack tags the cuisine's best-known dishes; a week must
  carry at least three, so trying a country's food is guaranteed, not incidental.

### 3.3 Per-day numeric targets (per adult reference portion, defaults)

| Metric | Rule |
|---|---|
| Energy | 1450–1650 kcal |
| Carbohydrate | ≤ 170 g |
| Fibre | ≥ 25 g |
| Protein | ≥ 70 g |
| Saturated fat | ≤ 15 g |
| Added sugar | 0 g |
| Refined-carb dishes | ≤ 1 per day |

Nutrition figures per recipe are author estimates; the validator enforces the
windows and reports the totals so drift is visible.

## 4. Design principles

1. **Deterministic.** Same cuisine + same week id + same recipe-pack version +
   same seed salt → identical plan. Committed plan files are the source of truth,
   so a plan never silently changes after it is published.
2. **Data-driven.** Cuisines are packs of recipe files. Adding a cuisine means
   adding a folder, not code.
3. **Static output.** The published site is still a single `index.html` with the
   plan inlined. No backend, no database. Works offline once loaded.
4. **Reuse what exists.** Same stack and conventions as shopping-assistant
   (Python 3.12, uv, Typer, pytest, ruff, ADRs in `docs/decisions/`), and the
   same Microsoft app registration and token cache.
5. **Secrets stay local.** The Microsoft token cache lives outside the repo.
   The repo is public; CI secrets are GitHub Actions secrets only.

### 4.1 Language decision: Python, not Node

Version 0.1 proposed Node because the only code in this repo was the JS inside
`index.html` and Node 20 could do everything with zero dependencies. After
reviewing shopping-assistant the trade-off changed:

| Consideration | Node | Python (uv) |
|---|---|---|
| Microsoft To Do auth | Write a device-code client from scratch (or add `@azure/msal-node`) | `msal` client, app registration, tenant setting and token cache already exist in shopping-assistant; copy one module |
| Your other projects | None are Node | shopping-assistant, budget-assistant are Python + uv + Typer with the same CLAUDE.md conventions |
| Scheduling | GitHub Actions only | GitHub Actions, plus the n8n instance already running for shopping-assistant |
| The web page | Vanilla JS either way | Vanilla JS either way; the build step only injects JSON into a template |
| Dependencies | Zero | A handful (typer, pyyaml, msal, httpx, jinja2), pinned by `uv.lock` |

The page itself stays vanilla HTML/CSS/JS with no build tooling, so there is no
JavaScript toolchain to maintain either way. Python wins on reuse. Node was a
fine answer for a standalone repo; it is the wrong answer next to an existing
Python ecosystem that already talks to Graph.

## 5. Repository layout

```
meal-plan/
  SPEC.md
  README.md                  # runbook (section 12)
  CLAUDE.md                  # conventions for Claude Code, same shape as shopping-assistant
  pyproject.toml             # uv project; CLI entry point `mealplan`
  uv.lock
  .python-version            # 3.12
  config/
    household.yaml           # people, targets, weekly rules, pantry staples, To Do mapping
    rotation.yaml            # cuisine order for automated weeks
  cuisines/
    kerala/
      pack.yaml              # id, name, version, slot composition, minimum counts
      recipes/*.yaml         # one recipe per file
    north-indian/ ...
  plans/
    2026-W44.json            # generated, committed, immutable once published
    manifest.json            # { current, next, builtAt }
  shopping/
    2026-W44.md              # human-readable list, grouped by aisle
    2026-W44.json            # machine list (what the To Do push consumes)
  src/mealplan/
    cli.py                   # Typer commands (section 13)
    config.py                # pydantic-settings; MS client id from env, like shopping-assistant
    models.py                # Recipe, Pack, Plan, Household (pydantic)
    packs.py                 # load + validate cuisine packs
    generate.py              # deterministic planner
    validate.py              # health-rule validator
    shopping.py              # aggregation, scaling, rounding
    integrations/mstodo.py   # Graph client: login copied from shopping-assistant + write path
    build.py                 # template + plans -> index.html
    web/template.html        # the UI; data injected at build time
  tests/
  docs/decisions/            # ADRs
  .github/workflows/
    weekly.yml               # Saturday cron + manual dispatch: plan, build, commit
    ci.yml                   # tests + stale-build check on push
  index.html                 # BUILD OUTPUT, committed (GitHub Pages serves it)
```

YAML for hand-authored files (recipes, config) because humans edit them; JSON for
generated files (plans, shopping) because the page consumes them.

## 6. Data model

### 6.0 Ingredient catalogue (`config/ingredients.yaml`)

One list of canonical ingredient names with unit, aisle, pantry-staple flag and
pack size. Recipes reference items by exact name and inherit the rest, so the
shopping list merges "shallots" from twelve recipes into one line and never
sees "shallot" and "small onions" as two items. The validator rejects a recipe
whose ingredient is not in the catalogue. Plans snapshot the resolved values.

### 6.1 Recipe (`cuisines/<id>/recipes/<recipe-id>.yaml`)

```yaml
id: kerala.lunch.netholi-peera
name: Netholi Meen Peera
slot: [lunch]
role: main               # main | side | carb | drink | treat
cuisine: kerala
protein: fish            # fish | chicken | beef | pork | egg | legume | dairy | none
lean: true               # required for beef/pork to be eligible
family: netholi          # variety key finer than protein (the fish, or the dish form)
tags: [high-protein, quick]
spice: medium
kidNote: Reduce green chilli; serve with a spoon of curd.
packable: true           # safe and pleasant from a lunchbox
prepMinutes: 15
cookMinutes: 20
effort: weekday          # weekday | weekend
nutrition: { kcal: 220, carbs: 6, fibre: 3, protein: 24, satFat: 4, sugar: 1 }
ingredients:             # per adult reference serving; names from the catalogue
  - { item: anchovies (netholi), qty: 120, unit: g }
  - { item: grated coconut, qty: 20, unit: g }
  - { item: kudampuli (Malabar tamarind), qty: 1, unit: pc }
  - { item: shallots (small onions), qty: 40, unit: g }
  - { item: turmeric powder, qty: 0.5, unit: tsp }
steps:
  - "..."
swaps:
  - { for: anchovies (netholi), use: "prawns, 120 g", note: sauté with pepper }
source: family recipe
```

A "meal" in a plan is a list of recipe ids: one main plus whatever the slot's
composition requires (section 6.2).

### 6.2 Cuisine pack (`pack.yaml`)

```yaml
id: kerala
name: Kerala
version: 1
slots:
  breakfast: { compose: [main], optional: [side] }
  lunch:     { compose: [main, side, carb], optional: [drink] }
  snack:     { compose: [main], optional: [drink] }
  dinner:    { compose: [main, carb], optional: [side] }
minimumRecipes: { breakfast: 10, lunch: 10, snack: 7, dinner: 10 }
```

`mealplan validate` refuses a pack below `minimumRecipes` or with a packable
lunch count below five.

### 6.3 Household (`config/household.yaml`)

```yaml
timezone: Australia/Melbourne
weekStarts: monday
shoppingDay: saturday
referenceKcal: 1550
people:
  - { name: Adult A, age: 47, targetKcal: [1600, 1800], spice: medium }
  - { name: Adult B, age: 41, targetKcal: [1600, 1800], spice: medium }
  - { name: Teen,    age: 14, targetKcal: [2000, 2400], spice: medium }
  - { name: Child,   age: 8,  targetKcal: [1400, 1600], spice: mild }
packedLunchDays: [mon, tue, wed, thu, fri]
targetsPerReferenceDay:
  kcal: [1450, 1650]
  carbs: [0, 170]
  fibre: [25, null]
  protein: [70, null]
  satFat: [0, 15]
  sugar: [0, 0]
  refinedCarbDishes: [0, 1]
weeklyRules:
  fishLunchesMin: 3
  chickenMax: 3
  redMeatMax: 1          # beef or pork, lean-tagged recipes only
  legumeDishesMin: 3
  eggMainsMax: 5         # meals whose main protein is egg
  treatsMax: 1
  vegDinnersMin: 2
  signatureDishesMin: 3   # recipes tagged signature (phase 5)
pantryStaples: [salt, turmeric, black pepper, mustard seeds, curry leaves, coconut oil,
                olive oil, cumin, coriander powder, chilli powder, garam masala]
todo:
  listName: Weekly Basket   # created on first push if missing
```

### 6.4 Plan output (`plans/2026-W44.json`)

```json
{
  "week": "2026-W44", "startDate": "2026-10-26",
  "cuisines": ["kerala"], "packVersions": { "kerala": 1 },
  "seed": "kerala:2026-W44:1:0", "salt": 0,
  "generatedAt": "2026-10-24T06:00:00+11:00", "generator": "1.0.0",
  "days": [
    { "date": "2026-10-26", "dow": "Mon", "cuisine": "kerala",
      "meals": { "breakfast": ["..."], "lunch": ["..."], "snack": ["..."], "dinner": ["..."] },
      "totals": { "kcal": 1520, "carbs": 150, "fibre": 31, "protein": 88, "satFat": 11, "sugar": 0 } }
  ],
  "weekChecks": { "fishLunches": 4, "chicken": 3, "redMeat": 1, "legumeDishes": 5, "eggs": 10, "treats": 1 },
  "recipes": { "kerala.lunch.netholi-peera": { "...full recipe snapshot..." } }
}
```

The plan embeds a **snapshot of every referenced recipe**, so the published page
and the shopping list never depend on later edits to the pack.

## 7. Plan generation (deterministic)

`mealplan plan --cuisine kerala --week 2026-W44 [--salt 0]`
`mealplan plan --cuisine kerala,thai --week next` (mixed week, see below)

1. Load household config and the pack(s); validate both.
2. Seed a PRNG (`random.Random(int(sha256(seedString), 16))`) from
   `"<cuisines>:<week>:<packVersions>:<salt>"`.
3. For each day, for each slot, for each role in the slot's composition:
   - Candidate set = recipes matching slot and role, minus hard exclusions:
     main already used this week, protein cap already hit, `effort: weekend` on
     a weekday, treat already used, non-packable lunch main on a packed-lunch
     day, red meat not tagged `lean`.
   - Score on soft goals: protein rotation (not yesterday's protein), ingredient
     overlap with the rest of the week (smaller shopping list, less waste), prep
     time on weekdays, days since last use across the previous two published
     plans, repeats of the same `family` within the week (so not three mackerel
     lunches), and a bonus when a lunch main can be made from the previous night's
     dinner main (same recipe or a declared `leftoverOf`).
   - Pick deterministically from the top three using the PRNG.
4. Run the day and week validators. On failure, bump an internal retry counter
   (which perturbs the PRNG) and regenerate, up to 25 times. If it still fails,
   exit non-zero and name the rule that could not be met. That is a data
   problem (pack too small or skewed), which the author fixes.
5. Write `plans/<week>.json` and update `plans/manifest.json`.
6. Print the week as a table.

**Choosing a cuisine.** `--cuisine` on the command line, or when omitted the
next entry from `config/rotation.yaml` (what the Saturday automation uses).
`mealplan cuisines` lists packs and recipe counts.

**Mixed weeks.** `--cuisine a,b` alternates cuisines by day (a,b,a,b,...);
`--cuisine a,b --mixed-by meal` would mix per slot. Single-cuisine weeks are
the default because the shopping list stays smaller. Rotation entries may also
be lists.

**Adding a cuisine.** `mealplan add-cuisine thai` scaffolds `cuisines/thai/`
with a `pack.yaml` and one example recipe per slot. Recipe authoring is a
Claude Code task: `docs/authoring.md` holds the prompt and the schema, and
`mealplan validate --cuisine thai` is the gate. Initial packs are drafted with
Claude, reviewed by you, then committed.

`--salt N` is the "I don't like this week, give me another" knob. It is recorded
in the plan file, so the result is still reproducible.

## 8. Recipe view

- CLI: `mealplan recipe kerala.lunch.netholi-peera` prints ingredients
  (scaled to the household) and steps.
- Web: tapping a meal card opens the recipe panel: ingredients for the
  household, steps, time, spice level, kid note, packable flag, swaps. Works
  without network because the data is inlined.

## 9. Shopping list

`mealplan shop --week 2026-W44 [--todo]`

1. For every meal in the plan, for every ingredient: `qty × Σ(person factors)`.
2. Normalise units (`g`, `ml`, `pc`; spoon measures kept for spices). Same
   `item` + same unit merge.
3. Split into **Buy** (non-staple), grouped by aisle in store order
   (produce → fish → meat → eggs/dairy → grains/legumes → pantry → spices), and
   **Check pantry** (staples used this week, with total quantity).
4. Round up to purchase amounts using `packSize` where present (eggs to 6,
   meat/fish to 50 g, bunches to whole bunches).
5. Each line records the recipes that use it.
6. Write `shopping/<week>.md` and `shopping/<week>.json`.
7. With `--todo`, push to Microsoft To Do (section 10).

The web page also renders the list with tick boxes (stored in `localStorage`,
per device) and a "Copy list" button as a no-setup fallback.

## 10. Microsoft To Do integration

- **Auth:** copy `integrations/mstodo.py`'s login and token handling from
  shopping-assistant. Same app registration (client id via
  `MEALPLAN_MS_CLIENT_ID`), tenant `consumers`, scope `Tasks.ReadWrite`,
  MSAL device-code flow, token cache at `~/.config/meal-plan/ms_token_cache.json`
  (mode 600). First run: `mealplan todo login`. Optionally point the cache path
  at shopping-assistant's `data/ms_token_cache.json` so one login serves both.
- **Write path (new):** `POST /me/todo/lists/{id}/tasks` with `title`,
  `body.content` and, in checklist mode, `checklistItems`.
- **One dedicated list**, named in `household.todo.listName` (default
  **"Weekly Basket"**), created on first push if it does not exist. Keeping the
  planner's tasks in their own list means the family's hand-written lists are
  never touched, and shopping-assistant can be pointed at "Weekly Basket" by
  adding it to its `GROCERY_MS_TODO_LIST` setting when price comparison is wanted.
- One task per Buy line, created in aisle order so the default list order is the
  store walk. Task title `Tomatoes — 1.2 kg`; body
  `Produce · used in: Thakkali Rasam, Egg Roast · meal-plan:2026-W44`.
- **Idempotent and polite:** before writing, delete open tasks carrying the
  previous week's `meal-plan:` marker in those lists. Tasks the family added by
  hand are never touched. Re-running the same week replaces its tasks.
- Pantry-check items go into one task "Check pantry (W44)" with checklist
  sub-items.
- shopping-assistant note: its sync treats a deleted task as "unseen", so items
  vanish from its list naturally; no change needed there.

## 11. Web page and publishing

- `src/mealplan/web/template.html` is the current UI, refactored to read its
  data from an inlined `<script id="plan-data" type="application/json">` block
  instead of a JS array. `mealplan build` injects the current and next week's
  plan and shopping list and writes `index.html`.
- Views: **This week** (day strip, today first, current meal highlighted, as
  now), **Next week** (visible once generated, so Saturday shopping works),
  **Recipe** panel, **Shopping** list with tick boxes. Cuisine badge per day.
- The page polls `plans/manifest.json?ts=<now>` every 15 minutes and reloads
  when `builtAt` changes, so a tablet left open picks up the new week on its own.
- The `localStorage` start-date hack is removed; the plan file carries dates.
- Publishing: push to `main`. GitHub Pages already serves the root of `main`.

## 12. Weekly workflow

### 12.1 Automatic (default)

`.github/workflows/weekly.yml`, cron Saturday 06:00 Australia/Melbourne
(expressed as two UTC crons to cover daylight saving, with a guard step that
exits unless local time is Saturday). Steps: `uv sync`, `mealplan plan --week
next` (cuisine from `rotation.yaml`), `mealplan shop --week next`,
`mealplan build`, commit and push. Also triggered by `workflow_dispatch` with
optional `cuisine` and `salt` inputs, so "run by hand" is a button on GitHub.

The To Do push is **not** in the Action by default, because device-code login
cannot happen in CI. Two options, choose later:

- (a) Local scheduled job on the Mac (launchd, or the n8n instance already
  running for shopping-assistant) that runs `git pull && mealplan shop --week
  next --todo` on Saturday morning. Uses the local token cache. Recommended.
- (b) Store the MSAL token cache as a GitHub Actions secret and run the push in
  CI. Works, but a personal-account refresh token expires after 90 days idle
  and must be re-uploaded; fragile.

### 12.2 By hand

```
mealplan plan --cuisine thai --week next --salt 0
mealplan shop --week next --todo
mealplan build
git add -A && git commit -m "Plan 2026-W45 (Thai)" && git push
```

`mealplan weekly [--cuisine ...] [--todo]` wraps the four steps.

## 13. CLI reference

| Command | Purpose |
|---|---|
| `mealplan plan --cuisine <id[,id]> --week <YYYY-Www\|next\|this> [--salt N]` | Generate and validate a week |
| `mealplan show --week <w>` | Print the week as a table |
| `mealplan recipe <recipe-id>` | Print a recipe scaled to the household |
| `mealplan shop --week <w> [--todo]` | Build the shopping list, optionally push to To Do |
| `mealplan todo login` | One-time Microsoft sign-in |
| `mealplan build` | Regenerate `index.html` |
| `mealplan weekly [--cuisine ...] [--todo] [--push]` | plan + shop + build (+ git push) |
| `mealplan validate [--cuisine <id>]` | Validate packs, config, plans |
| `mealplan cuisines` | List packs and recipe counts |
| `mealplan add-cuisine <id>` | Scaffold a new pack |

## 14. Testing

- Generator: same inputs → identical plan (golden file); salt changes the plan;
  validator failures name the rule; packed-lunch days never get a non-packable
  main; red meat never exceeds the cap and is always `lean`.
- Validator: fixtures that break each rule are rejected.
- Shopping: unit merge, scaling by the household sum, staple separation,
  rounding, aisle-to-list mapping.
- To Do: Graph client tested against a stubbed `httpx` transport; marker-based
  cleanup only deletes our tasks; no test ever hits the network.
- Build: output contains the plan JSON and no template placeholders; CI fails
  if the committed `index.html` is stale relative to `plans/`.

## 15. Phased delivery

| Phase | Deliverable | Done when |
|---|---|---|
| 0 ✅ | uv project, models, validator, Kerala pack migrated from the 28 hardcoded days (108 recipes), generator, build, CI | `index.html` is regenerated from data and looks like today |
| 1 ✅ | Ingredient catalogue, quantities + nutrition + steps for all Kerala recipes, shopping list (md + json), in-page list with tick boxes | A week's list prints grouped by aisle |
| 2 ✅ | Recipe panel in the page, recipe CLI | Every meal opens a recipe |
| 3 ✅ | Microsoft To Do push into the "Weekly Basket" list (ADR 0003) | `--todo` fills the list on the phone |
| 4 ✅ | Saturday automation (Actions cron, manual dispatch, rotation) and local launchd To Do job (ADR 0004) | A week appears on the tablet with no manual step |
| 5 ✅ | Ten cuisine packs (Kerala, North Indian, Sri Lankan, Thai, Mediterranean, Japanese, Middle Eastern, Korean, Mexican, Vietnamese), 44 recipes each except Kerala's 108, authored against the catalogue with signature dishes badged; `mealplan trial` dry-runs a pack. Italian and Chinese remain on request | Each pack passes `validate` and `trial` over 8 weeks |
| 6 | Kids' lunchbox slot, mixed-by-meal weeks, leftover-driven lunches, nutrition summary chart, print view | — |

## 16. Decisions log

| # | Decision | Source |
|---|---|---|
| 1 | Personal Microsoft account, reuse shopping-assistant's app registration and device-code login | Review 1 |
| 2 | Per-person energy targets by age (47, 41, 14, 8) drive portion factors | Review 1 |
| 3 | Lunches both at home and packed; weekday lunch mains must be packable | Review 1 |
| 4 | Beef and pork allowed, lean-tagged only, ≤ 1/week, within the sat-fat cap | Review 1 |
| 5 | Cuisine chosen per run or from rotation; new cuisines added by scaffold + Claude authoring + validator | Review 1 |
| 6 | Mixed weeks are an option (`--cuisine a,b`), single-cuisine is the default | Review 1 |
| 7 | Auto-generate every Saturday via GitHub Actions; manual dispatch and CLI also available | Review 1 |
| 8 | Timezone Australia/Melbourne | Review 1 |
| 9 | Python 3.12 + uv, not Node (section 4.1) | Review 1 |
| 10 | To Do push goes to one new dedicated list, "Weekly Basket" | Review 2 |
| 11 | Ingredient names come from one catalogue (`config/ingredients.yaml`); recipes reference it | Phase 1 |
| 12 | Nutrition values are estimates, corrected as recipes are cooked; no up-front review | Review 3 |
| 13 | Energy targets stand as set in `household.yaml` | Review 3 |
| 14 | To Do: one task per item in aisle order; pantry staples as one task with checklist sub-items | Review 3 |
| 15 | To Do push runs on the Mac (n8n or launchd) on Saturday mornings, not in GitHub Actions; separate token cache under `~/.config/meal-plan/` | Review 3 |
| 16 | shopping-assistant syncs "Weekly Basket" too, so the basket gets price-compared | Review 3 |
| 17 | Automation: GitHub Actions, Saturday 06:00 Australia/Melbourne, for the week starting Monday | Review 3 |
| 18 | Lunches stay separate dishes (no doubled dinners); kids' lunchbox slot is a later phase | Review 3 |
| 19 | Phase 5 authors five packs: North Indian, Sri Lankan, Thai, Mediterranean, Middle Eastern; the rest on request. Agents write from their own knowledge (no fetching); gates are schema check, pack validation, a generated week, and a skim | Review 3 |
| 21 | `carbs` means available carbohydrate (fibre excluded) and `sugar` added sugar; the planner steers all metrics from breakfast onward using slot medians as a lookahead | Phase 5 |
| 20 | Every pack carries the cuisine's signature dishes, tagged `signature` with the traditional dish recorded; weekly rule `signatureDishesMin: 3`; iconic dishes that cannot be adapted are the week's single treat; the page badges them with one sentence | Review 3 |

## 17. Open questions

None. Everything raised so far is settled in the decisions log (section 16).

## 18. Non-goals

- Medical accuracy of nutrition values; they are estimates for steering, not a
  clinical tool.
- Accounts, multi-user sync, or a backend. Device-side state (tick boxes) stays
  per device.
- Supermarket price lookup or ordering. That is shopping-assistant's job and it
  gets the list through To Do.
