from __future__ import annotations

from pathlib import Path

import pytest

from mealplan.config import Paths, load_household
from mealplan.models import Household, LoadedPack
from mealplan.packs import load_pack

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def root_paths() -> Paths:
    return Paths(ROOT)


@pytest.fixture(scope="session")
def household(root_paths: Paths) -> Household:
    return load_household(root_paths)


@pytest.fixture(scope="session")
def kerala(root_paths: Paths) -> LoadedPack:
    return load_pack(root_paths.cuisines_dir, "kerala")
