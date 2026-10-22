# ADR 0002: Deterministic generation, plans committed with recipe snapshots

Date: 2026-10-23. Status: accepted.

## Context

The plan has to be repeatable: the same request should give the same week, and a week that has
been published to the kitchen tablet must not change underneath the family when a recipe file is
edited or the algorithm improves.

## Decision

1. `generate()` seeds `random.Random` from
   `sha256("<cuisines>:<week>:<pack versions>:<salt>")`. Candidates are filtered by hard rules,
   scored by soft goals, sorted by (score desc, id asc), and the PRNG picks among the top three.
   Validation failures perturb the seed and retry up to 25 times, then fail with the rule names.
2. Every generated week is written to `plans/<week>.json` **with a snapshot of each recipe it
   references** and committed. The page and the shopping list read only the plan file.
3. `index.html` is derived from the committed plans and is itself committed; CI fails when it is
   stale (`mealplan build --check`). Its content version is a hash of the plan files, which the
   page polls to reload itself.

## Consequences

- Reproducibility does not depend on the generator staying byte-for-byte stable; the committed
  plan is the truth. Determinism is a convenience for regeneration and testing.
- Fixing a recipe does not change past weeks. Bumping `pack.yaml: version` changes future seeds.
- `--salt` is the "give me another week" knob and is recorded in the plan.
