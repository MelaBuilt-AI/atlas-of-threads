from __future__ import annotations

import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
FIXTURES = ROOT / "fixtures"


@pytest.fixture
def fixtures_dir() -> Path:
    return FIXTURES


@pytest.fixture
def origin_gold() -> dict:
    return json.loads(
        (FIXTURES / "graphs" / "origin-conversation.gold.json").read_text(
            encoding="utf-8"
        )
    )


@pytest.fixture
def simple_gold() -> dict:
    return json.loads(
        (FIXTURES / "graphs" / "simple.gold.json").read_text(encoding="utf-8")
    )


@pytest.fixture
def store_dir(tmp_path: Path) -> Path:
    return tmp_path / "data"
