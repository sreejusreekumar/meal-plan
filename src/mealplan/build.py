"""Turn committed plans into the published page.

`index.html` = template + an inlined JSON blob holding the current and next week (with their
recipe snapshots), the cuisine packs' labels and rules, and a content version the page polls
for. The output is deterministic for a given set of plan files, so CI can check it is fresh.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from mealplan.config import Paths, load_household, load_yaml
from mealplan.models import Household, Pack, Plan
from mealplan.weeks import today_in, week_id
from mealplan.weeks import week_start as ws

PLACEHOLDER = "__PLAN_DATA__"


def load_plan(path: Path) -> Plan:
    return Plan.model_validate_json(path.read_text(encoding="utf-8"))


def plan_path(p: Paths, week: str) -> Path:
    return p.plans_dir / f"{week}.json"


def all_plans(p: Paths) -> list[Plan]:
    if not p.plans_dir.exists():
        return []
    plans = [load_plan(f) for f in p.plans_dir.glob("*-W*.json")]
    return sorted(plans, key=lambda pl: pl.start_date)


def save_plan(p: Paths, plan: Plan) -> Path:
    p.plans_dir.mkdir(parents=True, exist_ok=True)
    out = plan_path(p, plan.week)
    out.write_text(
        plan.model_dump_json(by_alias=True, exclude_none=True, indent=2) + "\n", encoding="utf-8"
    )
    return out


def content_version(plans: list[Plan]) -> str:
    h = hashlib.sha256()
    for plan in plans:
        h.update(plan.model_dump_json(by_alias=True, exclude_none=True).encode("utf-8"))
    return h.hexdigest()[:12]


def select_weeks(plans: list[Plan], today: date) -> tuple[str | None, str | None, list[Plan]]:
    """(current week id, next week id, plans to embed). Current is the plan covering today,
    else the most recent one that has already started; next is the following ISO week if
    a plan exists for it. With no plan started yet, the earliest future plan is embedded."""
    by_week = {pl.week: pl for pl in plans}
    this_week = week_id(today)
    next_week = week_id(ws(this_week) + timedelta(days=7))
    current = this_week if this_week in by_week else None
    if current is None:
        started = [pl for pl in plans if pl.start_date <= today.isoformat()]
        if started:
            current = started[-1].week
    nxt = next_week if next_week in by_week else None
    embed: list[Plan] = []
    if current:
        embed.append(by_week[current])
    if nxt and nxt != current:
        embed.append(by_week[nxt])
    if not embed and plans:
        embed.append(plans[0])
    return current, nxt, embed


def pack_meta(p: Paths, cuisine_ids: set[str]) -> dict[str, dict]:
    meta: dict[str, dict] = {}
    for cid in sorted(cuisine_ids):
        f = p.cuisines_dir / cid / "pack.yaml"
        if f.exists():
            pack = Pack.model_validate(load_yaml(f))
            meta[cid] = {"name": pack.name, "slotLabels": pack.slot_labels, "rules": pack.rules}
        else:
            meta[cid] = {"name": cid.title(), "slotLabels": {}, "rules": []}
    return meta


def page_data(p: Paths, household: Household, plans: list[Plan], today: date) -> dict:
    current, nxt, embed = select_weeks(plans, today)
    cuisines = {c for pl in embed for c in pl.cuisines}
    return {
        "version": content_version(plans),
        "household": {
            "timezone": household.timezone,
            "servings": household.servings,
            "people": [{"name": pp.name, "age": pp.age} for pp in household.people],
        },
        "packs": pack_meta(p, cuisines),
        "manifest": {"current": current, "next": nxt},
        "weeks": [pl.model_dump(by_alias=True, exclude_none=True) for pl in embed],
    }


def manifest(plans: list[Plan], today: date) -> dict:
    current, nxt, _ = select_weeks(plans, today)
    return {
        "version": content_version(plans),
        "current": current,
        "next": nxt,
        "weeks": [
            {
                "week": pl.week,
                "startDate": pl.start_date,
                "cuisines": pl.cuisines,
                "file": f"{pl.week}.json",
            }
            for pl in plans
        ],
    }


def render_page(template: str, data: dict) -> str:
    if PLACEHOLDER not in template:
        raise ValueError("template has no __PLAN_DATA__ placeholder")
    blob = json.dumps(data, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return template.replace(PLACEHOLDER, blob, 1)


def build(p: Paths, today: date | None = None, write: bool = True) -> tuple[str, dict]:
    """Returns (html, manifest). With write=True also writes index.html and plans/manifest.json."""
    household = load_household(p)
    today = today or today_in(household.timezone)
    plans = all_plans(p)
    data = page_data(p, household, plans, today)
    html = render_page(p.template_file.read_text(encoding="utf-8"), data)
    man = manifest(plans, today)
    if write:
        p.index_html.write_text(html, encoding="utf-8")
        p.plans_dir.mkdir(parents=True, exist_ok=True)
        p.manifest_file.write_text(json.dumps(man, indent=2) + "\n", encoding="utf-8")
    return html, man


def is_stale(p: Paths, today: date | None = None) -> bool:
    html, man = build(p, today=today, write=False)
    if not p.index_html.exists() or p.index_html.read_text(encoding="utf-8") != html:
        return True
    if not p.manifest_file.exists():
        return True
    return json.loads(p.manifest_file.read_text(encoding="utf-8")) != man
