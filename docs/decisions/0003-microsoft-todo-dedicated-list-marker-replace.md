# ADR 0003: Microsoft To Do push into a dedicated list, marker-based replace

Date: 2026-10-23. Status: accepted.

## Context

The weekly shopping list should land on the family's phones without retyping. The household
uses Microsoft To Do on a personal account, and shopping-assistant already holds a public-client
app registration with device-code login for that account. Hand-written To Do lists must never be
disturbed.

## Decision

- Reuse the app registration (client id via `MEALPLAN_MS_CLIENT_ID` in a gitignored `.env`),
  tenant `consumers`, scope `Tasks.ReadWrite`, MSAL device-code flow. The token cache is a
  separate file under `~/.config/meal-plan/` (mode 600), so the two tools never log each other
  out.
- All tasks go to one dedicated list, "Weekly Basket" (`household.todo.listName`), created on the
  first push.
- One task per item to buy, title `item — quantity`, body `Aisle · used in: recipes ·
  meal-plan:<week>`. Pantry staples become one task "Check pantry — <week>" with checklist
  sub-items.
- Idempotent replace: before creating, delete every *open* task in the list whose body carries a
  `meal-plan:` marker. Completed tasks and tasks without the marker are left alone.
- Tasks are created in reverse aisle order (pantry first, then last aisle … first aisle) because
  To Do shows newest first; the list then reads as the store walk from the top.
- The push runs on the Mac, by hand or from a local scheduled job; GitHub Actions never holds the
  token.

## Consequences

- Re-running `mealplan shop --week next --todo` after a reroll replaces the week's tasks cleanly.
- shopping-assistant can price the basket by adding "Weekly Basket" to its synced lists; its sync
  treats our deleted tasks as gone, so nothing lingers there.
- A deleted or renamed list is recreated on the next push rather than failing the run.
