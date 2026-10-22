# Authoring a cuisine pack

A pack is `cuisines/<id>/pack.yaml` plus one YAML file per recipe in `cuisines/<id>/recipes/`.
Scaffold one with `uv run mealplan add-cuisine <id>`, fill it, then gate it with
`uv run mealplan validate -c <id>`. The planner needs at least 10 breakfast, 10 lunch, 7 snack and
10 dinner mains, with 5 or more packable lunches, before it will use a pack.

## Recipe file

```yaml
id: thai.lunch.pla-neung-manao          # <pack>.<slot>.<slug>; file name is <id>.yaml
name: Steamed fish with lime and chilli
slot: [lunch]                           # may list several slots
role: main                              # main | side | carb | drink | treat
cuisine: thai
protein: fish                           # fish | chicken | beef | pork | egg | legume | dairy | none
lean: false                             # must be true for beef/pork
family: white-fish                      # variety key: the fish or dish form; avoid repeats in a week
tags: [quick, high-protein]
spice: medium                           # mild | medium | hot (household default is medium)
kidNote: Serve the child's portion without the chilli dressing.
packable: true                          # pleasant from a lunchbox (required Mon–Fri)
prepMinutes: 10
cookMinutes: 15
effort: weekday                         # weekend = long cook or treat; never picked Mon–Fri
treat: false
refinedCarb: false                      # white rice, noodles, pastry... max 1 dish/day
nutrition: { kcal: 520, carbs: 48, fibre: 7, protein: 38, satFat: 3, sugar: 4 }
components:                             # what is on the plate, shown on the page
  - "Primary: 150 g steamed barramundi with lime, garlic and chilli"
  - 1 cup stir-fried morning glory or bok choy
  - 3/4 cup brown jasmine rice
ingredients:                            # per adult reference serving (~1550 kcal/day)
  - { item: barramundi fillet, qty: 150, unit: g, aisle: fish, packSize: 50 }
  - { item: lime, qty: 1, unit: pc, aisle: produce }
  - { item: garlic, qty: 2, unit: pc, aisle: produce, staple: true }
  - { item: brown jasmine rice, qty: 60, unit: g, aisle: grains }
steps:
  - Season the fish, steam 10 minutes.
  - Whisk lime, garlic, chilli, fish sauce; spoon over.
swaps:
  - { for: barramundi fillet, use: snapper or ling, note: same timing }
source: family recipe / adapted from ...
```

Rules of thumb for this household (pre-diabetic, borderline LDL/TG):

- Whole grains only, measured. No sugary drinks, no added sugar in snacks.
- Every lunch and dinner carries at least one vegetable dish.
- Fish-forward lunches; chicken a few times a week; lean red meat occasionally; legumes often.
- Coconut milk, cream, butter and oil are measured, not free. Aim for satFat ≤ 15 g per day.
- Breakfast ~350–390 kcal, lunch ~510–550, snack ~100–130, dinner ~470–510, so any
  combination lands inside the 1450–1650 kcal daily window.
- Spice is medium by default. Add a `kidNote` whenever chilli is in the dish.

## Drafting with Claude Code

Paste this into Claude Code from the repo root:

> Create a `<cuisine>` cuisine pack under `cuisines/<id>/` following `docs/authoring.md`.
> Write 12 breakfasts, 12 lunches (at least 8 packable), 8 snacks and 12 dinners as separate
> recipe files, each with realistic per-serving nutrition, ingredient quantities per adult serving
> with aisles, 3–6 steps and a `family`. Respect the household rules in `config/household.yaml`.
> Then run `uv run mealplan validate -c <id>` and fix anything it reports.

Review the recipes before committing: nutrition numbers are estimates and should look plausible to
you. Bump `pack.yaml: version` whenever you change nutrition values or ids of an existing pack.
