"""
Shared fixtures.

Tests fall into three bands by what they need on disk:

  workbook only   — runs from a clean clone; the .xlsx is committed
  fetched source  — needs `python pipeline/fetch.py` to have run
  pipeline output — needs the full pipeline to have run

Anything unavailable is SKIPPED, not failed, so a clean clone can still run the
band that matters most. CI runs the pipeline first, so all three bands execute
there.

Tests are also split along a second axis (GAPS.md §6):

  invariants      — must hold for ANY corpus: no residual markers, reading
                    order consistent, identifiers stable, store split clean
  per-corpus pins — expected counts and floors, which are properties of one
                    text, not of the pipeline

The pins live in `fixtures/{corpus}.yaml`, not in test code. `--corpus`
selects which text is under test (default: tajrid); the `expected` fixture
loads that corpus's file, and `expect(...)` SKIPS — naming the missing key —
when the corpus has not supplied a value. A new text therefore runs every
invariant on day one and earns its pins by writing its own fixture file,
instead of failing assertions written for a different book.
"""

from __future__ import annotations

import collections
import json
import sys
from pathlib import Path

import pytest
import yaml

PIPELINE = Path(__file__).resolve().parent.parent
ROOT = PIPELINE.parent
sys.path.insert(0, str(PIPELINE))

CACHE = PIPELINE / "cache"
BUILD = PIPELINE / "build"
FIXTURES = Path(__file__).resolve().parent / "fixtures"
WORKBOOK = ROOT / "Tajrid_frequency_tables.xlsx"
WORKBOOK_CACHED = CACHE / "Tajrid_frequency_tables.xlsx"


def pytest_addoption(parser):
    parser.addoption(
        "--corpus",
        default="tajrid",
        help="corpus under test; selects pipeline/build/{corpus} and "
        "pipeline/tests/fixtures/{corpus}.yaml",
    )


def _need(path: Path, what: str):
    if not path.exists():
        pytest.skip(f"{what} not present ({path.name}) — run the pipeline first")
    return path


@pytest.fixture(scope="session")
def corpus(request) -> str:
    """The corpus id under test. Everything corpus-scoped derives from this."""
    return request.config.getoption("--corpus")


@pytest.fixture(scope="session")
def expected(corpus):
    """
    The per-corpus expectations, as a callable: `expected("records.total")`
    returns the value or SKIPS naming the key. Dotted keys walk the YAML.
    An absent file behaves as an empty one — every pin skips, every
    invariant still runs.
    """
    path = FIXTURES / f"{corpus}.yaml"
    data = yaml.safe_load(path.read_text(encoding="utf-8")) if path.exists() else {}

    def expect(dotted: str):
        node = data or {}
        for part in dotted.split("."):
            if not isinstance(node, dict) or part not in node:
                pytest.skip(
                    f"no expectation `{dotted}` in fixtures/{corpus}.yaml — "
                    "supply one to pin this for the corpus"
                )
            node = node[part]
        return node

    return expect


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
def records(corpus):
    path = _need(BUILD / corpus / "records.json", "segmented records")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def bindings(corpus):
    path = _need(BUILD / corpus / "bindings.json", "token bindings")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def disambiguated(corpus):
    """
    Context analysis for the corpus under test. Session-scoped and shared so
    that every context test agrees about whether the provider is present —
    see test_context_morphology for why that matters.
    """
    path = BUILD / corpus / "disambiguated.json"
    if not path.exists():
        pytest.skip("no context analysis — run pipeline/disambiguate.py before build.py")
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture(scope="session")
def rawd_records():
    """
    The second corpus, by name and on purpose: CI segments it as the
    generalisation canary regardless of which corpus is under test.
    """
    path = _need(BUILD / "rawd" / "records.json", "second corpus records")
    return json.loads(path.read_text(encoding="utf-8"))
