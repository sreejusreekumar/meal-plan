# ADR 0004: Weekly automation split between GitHub Actions and a Mac launchd job

Date: 2026-10-23. Status: accepted.

## Context

The week should appear on the kitchen tablet and the shopping list on the phones every Saturday
without anyone running commands. Generating and publishing needs only the repo; pushing to
Microsoft To Do needs a user token obtained by device-code sign-in, which cannot happen in CI.

## Decision

- **GitHub Actions** (`.github/workflows/weekly.yml`) runs `mealplan weekly --week next`
  on Saturday 06:00 Australia/Melbourne, validates, checks the build is fresh, and commits
  `plans/`, `shopping/` and `index.html`. Two UTC crons plus a local-time guard handle daylight
  saving. A manual "Run workflow" button accepts week, cuisine, salt and force. GitHub Pages
  serves the committed page, so the tablet refreshes itself within fifteen minutes.
- **The Mac** runs `scripts/weekly-todo.sh` via launchd (`com.mealplan.todo`) at 06:30 local:
  `git pull --ff-only` then `mealplan todo push --week next`. The token cache stays on the Mac.
  launchd runs a missed job on wake if the Mac was asleep; a Mac that was powered off skips that
  week, and the push is one command by hand.
- `mealplan weekly` is the single routine both use: plan (unless the week exists), shop, build,
  optional `--todo`. It is also the manual runbook.

## Consequences

- No secrets in GitHub. The repo stays safe to keep public.
- The bot commit uses `GITHUB_TOKEN`, which does not trigger the CI workflow; the weekly
  workflow runs the same validation itself.
- If the Action and a manual run both plan the same week, the first wins; the other sees the
  plan exists and only rebuilds. `--force` is the explicit override.
