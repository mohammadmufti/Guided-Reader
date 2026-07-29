"""
Shared fixtures.

Tests fall into three bands by what they need on disk:

  workbook only   — runs from a clean clone; the .xlsx is committed
  fetched source  — needs `python pipeline/fetch.py` to have run
  pipeline output — needs the full pipeline to have run

Anything unavailable is SKIPPED, not failed, so a clean clone can still run the
band that matters most. CI runs the pipeline first, so all three bands execute
there.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import pytest

PIPELINE = Path(__file__).resolve().parent.parent
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))

CACHE = PIPELINE / "cache"
BUILD = PIPELINE / "build"
WORKBOOK = ROOT / "Tajrid_frequency_tables.xlsx"
WORKBOOK_CACHED = CACHE / "Tajrid_frequency_tables.xlsx"


def _need(path: Path, what: str):
    if not path.exists():
        pytest.skip(f"{what} not present ({path.name}) — run the pipeline first")
    return path


@pytest.fixture(scope="session")
def surface():
    """The Surface sheet as a list of dicts. The workbook is committed."""
    import pandas as pd

    path = WORKBOOK if WORKBOOK.exists() else WORKBOOK_CACHED
    _need(path, "lexicon workbook")
    return pd.read_excel(path, sheet_name="Surface").to_dict("records")


@pytest.fixture(scope="session")
def by_search_key(surface):
    out: dict[str, list[dict]] = collections.defaultdict(list)
    for row in surface:
        out[str(row["search_key"])].append(row)
    return out


@pytest.fixture(scope="session")
def records():
    path = _need(BUILD / "tajrid" / "records.json", "segmented records")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def bindings():
    path = _need(BUILD / "tajrid" / "bindings.json", "token bindings")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rawd_records():
    path = _need(BUILD / "rawd" / "records.json", "second corpus records")
    return json.loads(path.read_text(encoding="utf-8"))
