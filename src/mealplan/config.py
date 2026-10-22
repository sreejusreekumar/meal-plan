"""Where things live and how to load the hand-edited config files."""

from __future__ import annotations

import os
from dataclasses import dataclass
from importlib import resources
from pathlib import Path

import yaml

from mealplan.models import Household


@dataclass(frozen=True)
class Paths:
    root: Path

    @property
    def config_dir(self) -> Path:
        return self.root / "config"

    @property
    def cuisines_dir(self) -> Path:
        return self.root / "cuisines"

    @property
    def plans_dir(self) -> Path:
        return self.root / "plans"

    @property
    def shopping_dir(self) -> Path:
        return self.root / "shopping"

    @property
    def household_file(self) -> Path:
        return self.config_dir / "household.yaml"

    @property
    def rotation_file(self) -> Path:
        return self.config_dir / "rotation.yaml"

    @property
    def manifest_file(self) -> Path:
        return self.plans_dir / "manifest.json"

    @property
    def index_html(self) -> Path:
        return self.root / "index.html"

    @property
    def template_file(self) -> Path:
        return Path(str(resources.files("mealplan") / "web" / "template.html"))


def find_root(start: Path | None = None) -> Path:
    """Repo root: MEALPLAN_ROOT if set, else the nearest ancestor with config/household.yaml."""
    env = os.environ.get("MEALPLAN_ROOT")
    if env:
        return Path(env).resolve()
    here = (start or Path.cwd()).resolve()
    for candidate in (here, *here.parents):
        if (candidate / "config" / "household.yaml").exists():
            return candidate
    return here


def paths(root: Path | None = None) -> Paths:
    return Paths(root or find_root())


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"{path}: expected a mapping at the top level")
    return data


def load_household(p: Paths) -> Household:
    return Household.model_validate(load_yaml(p.household_file))


def load_rotation(p: Paths) -> list[str]:
    if not p.rotation_file.exists():
        return []
    entries = load_yaml(p.rotation_file).get("rotation") or []
    return [str(e).strip() for e in entries if str(e).strip()]
