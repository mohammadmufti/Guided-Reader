#!/usr/bin/env python3
"""
The al-Tajrid frequency workbook. AN EXCEPTION, ISOLATED HERE ON PURPOSE.

`Tajrid_frequency_tables.xlsx` is a hand-built artefact for ONE text. It was a
one-time patch that got al-Tajrid to a shippable state, and it is not the
strategy for anything after it -- there is no such workbook for the Muwatta',
and there will not be one for the text after that. Later corpora derive their
inventory from a vocalised parent edition (`Lexicon.seed_from_witness`) and
take meaning from the shared glossary.

None of that makes the workbook wrong for al-Tajrid. It is the best thing that
book has, it is measurably good -- 97.2% Tier 1+2 against 96.6% for the derived
path -- and it holds 21,028 curated glosses that nothing else can produce. It
should keep being used. It should just not be BUILT INTO the pipeline, because
one text's exceptional input becomes everyone's problem the moment a general
module knows the name of a spreadsheet column.

So this module is the boundary. Everything that knows about `.xlsx`, about
sheets named `Surface` and `Review`, about a `voc_source` column or a
pipe-separated `candidates` string, lives here and nowhere else. `bind.py`
receives plain dictionaries and cannot tell where they came from.

WHAT TO DO WITH THIS FILE WHEN THE NEXT TEXT ARRIVES: nothing. That is the
point. A new corpus adds no code here and no branch anywhere else; it simply
declares no `sources.lexicon`, and the derived path takes over.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

# `voc_source` values meaning "the workbook picked this, it did not witness it".
RE_REVIEW_CANDIDATE = re.compile(r"^\s*(.+?)\s*\(\d+\)\s*$")


def read_surface(workbook: Path) -> list[dict]:
    """
    Curated readings for al-Tajrid, most frequent first.

    Returns rows with only the keys the binder needs, so a change to the
    spreadsheet's shape stops here instead of propagating. Sorted on the way
    out because the binder's fallback tier depends on frequency order and
    should not have to know that.
    """
    rows = pd.read_excel(workbook, sheet_name="Surface").to_dict("records")
    rows.sort(key=lambda r: -int(r["freq"]))
    return [
        {
            "search_key": str(r["search_key"]),
            "vocalized": str(r["vocalized"]),
            "unvocalized": str(r["unvocalized"]),
            "freq": int(r["freq"]),
            "pos": r["pos"],
            "voc_source": r.get("voc_source"),
        }
        for r in rows
    ]


def read_review(workbook: Path) -> tuple[set[str], dict[str, set[str]]]:
    """
    The Review sheet: forms flagged ambiguous, and their plausible readings.

    Returns (flagged_surfaces, plausible_by_surface).

    The sheet also carries frequencies from a REFERENCE corpus, and those are
    deliberately dropped. Held out on 50,538 tokens they score 69.1% against
    our own 70.1%, and where the two disagree it is a coin flip -- 2,465 to
    2,479. What the sheet is good for is saying which readings are plausible AT
    ALL; restricting candidates to its list and then ranking by our own
    frequency scores 70.6%. Reading the column here and discarding it is how
    that finding stays enforced rather than remembered.
    """
    sheet = pd.read_excel(workbook, sheet_name="Review")
    flagged = set(sheet["surface"].astype(str))

    plausible: dict[str, set[str]] = {}
    for row in sheet.to_dict("records"):
        surface_form = str(row.get("surface") or "")
        raw = row.get("candidates")
        if not surface_form or not isinstance(raw, str):
            continue
        forms = set()
        for part in raw.split("|"):
            m = RE_REVIEW_CANDIDATE.match(part)
            if m:
                forms.add(m.group(1))
        if forms:
            plausible[surface_form] = forms
    return flagged, plausible


def read_lexicography(workbook: Path) -> list[dict]:
    """Raw Surface rows for `glossary.py`, which lifts meaning out once."""
    return pd.read_excel(workbook, sheet_name="Surface").to_dict("records")
