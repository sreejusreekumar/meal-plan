# ADR 0001: Python 3.12 + uv, reusing shopping-assistant's Microsoft Graph client

Date: 2026-10-23. Status: accepted.

## Context

The repo held a single `index.html` with the plan hardcoded in JavaScript. The first draft of the
spec proposed Node 20 with zero dependencies, because that matched the only code present.

The sibling project `~/Projects/shopping-assistant` is Python 3.12 managed by uv, with Typer,
pytest, ruff and ADRs, and it already contains a Microsoft To Do client: MSAL device-code login
against the `consumers` tenant, an app registration, a token cache, and a scheduled sync that
reads the lists "Groceries", "Meat & Fish" and "Vegetables & Fruits" for price comparison.

## Decision

Build the planner in Python 3.12 with uv, mirroring shopping-assistant's conventions. Copy its
Graph login and add the write path. The published page stays vanilla HTML/CSS/JS with no build
tooling; Python only injects JSON into a template.

## Consequences

- One login and one app registration serve both tools.
- The weekly flow becomes meal-plan → To Do (by aisle) → shopping-assistant price comparison,
  with no code coupling between the projects.
- A handful of pinned dependencies (typer, pyyaml, pydantic, rich; msal and httpx in phase 3)
  instead of zero. Acceptable.
