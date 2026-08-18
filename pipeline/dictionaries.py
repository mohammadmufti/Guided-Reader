"""
What the classical Arabic dictionaries have in common.

Small on purpose. This module exists because a SECOND source needed the same
two things, not in anticipation of one — the alif variant lived in `lisan.py`
until al-Nihāya turned out to file its roots the same way, which is the point
at which sharing stops being speculative.

What is deliberately NOT here: entry parsing, sense structure, sigla. Those
differ per book and belong with the book. `ADDENDUM-adding-sources.md` warns
that wanting to edit shared code to add a source is a bug in the configuration
surface; the corollary is that hoisting per-source logic into a shared module
is the same bug wearing a different hat.
"""

from __future__ import annotations

import re

from normalise import root_variants

# ي ى و ا — the four spellings a final weak radical takes.
WEAK = ("\u064a", "\u0649", "\u0648", "\u0627")


def dict_root_variants(root: str) -> list[str]:
    """
    `root_variants()` plus the bare-alif spelling of a final-weak root.

    Both classical dictionaries ingested here file final-weak roots under a
    bare alif — صلا, not صلو or صلى. Lisān does it for 390 of its three-letter
    heads, al-Nihāya for 338 of its roots. `root_variants()` treats the weak
    axis as ي/ى/و only, so without this every final-weak root in every corpus
    misses its article and the reader is shown a section with nothing in it.

    Measured on al-Tajrīd's rooted forms: Lisān 88.8% -> 96.4%, Nihāya
    84.0% -> 94.4%.

    WHY NOT WIDEN `root_variants()` ITSELF. Lane holds 213 alif-final roots of
    its own, so the shared function would move live Lane resolution and
    silently re-point entries that are currently correct. A filing convention
    is a property of the book that uses it. If Lane should gain the same
    variant, that is its own change with its own held-out measurement.

    Only ever ADDS: every variant the shared function produces survives.
    """
    out = list(root_variants(root))
    for v in list(out):
        if v and v[-1] in WEAK:
            for w in WEAK:
                cand = v[:-1] + w
                if cand not in out:
                    out.append(cand)
    return out


# Sentence enders. The Arabic comma and semicolon are NOT here: both authors
# string clauses with و and ؛ for pages at a time, and splitting on those
# reproduces the very fragments the rejoin exists to repair.
SENTENCE_END = re.compile(r"(?<=[.؟!])\s+")

# A unit shorter than this is almost always a stranded quotation fragment
# rather than a sense, and is merged forward into the next one.
MIN_UNIT_CHARS = 25


def sentences(text: str) -> list[str]:
    """
    Continuous prose -> display units.

    THE DEFECT THIS EXISTS TO FIX. The `#` lines in these Shamela conversions
    are not paragraphs. Across Lisān, 52.5% run under 60 characters and 55.5%
    do not end in terminal punctuation, because the conversion breaks around
    block quotations and verse. Rendered raw, the ṣalāh article opens as one
    sentence in three pieces, the third beginning with a comma. Rejoining and
    splitting here recovers `الصلاة: الركوع والسجود.` as the opening unit.
    """
    out: list[str] = []
    merged = 0
    for part in SENTENCE_END.split(text):
        part = part.strip()
        if not part:
            continue
        if out and len(part) < MIN_UNIT_CHARS:
            out[-1] = f"{out[-1]} {part}"
            merged += 1
        else:
            out.append(part)
    sentences.merged = merged  # type: ignore[attr-defined]
    return out


# Anything that survives into a rendered run means the strip config is wrong
# and everything downstream is built on garbage. ADDENDUM §A.5 calls this "the
# single most useful signal that a config is right", so it is checked rather
# than trusted.
RESIDUAL = re.compile(r"###|~~|PageV\d|<div|</?span|\bms\d{3,}\b|\[\s*ص\s*:")


def audit(roots: dict[str, dict]) -> list[str]:
    """Invariants every dictionary in the shared store must satisfy."""
    problems = []
    hits = [
        (r, run["v"][:60])
        for r, payload in roots.items()
        for e in payload["entries"]
        for s in e["senses"]
        for run in s["runs"]
        if RESIDUAL.search(run["v"])
    ]
    if hits:
        problems.append(
            f"{len(hits)} runs carry residual markers, e.g. {hits[0][0]}: {hits[0][1]!r}"
        )
    empty = [r for r, p in roots.items() if not p["entries"][0]["senses"]]
    if empty:
        problems.append(f"{len(empty)} roots have no senses, e.g. {empty[:3]}")
    return problems
