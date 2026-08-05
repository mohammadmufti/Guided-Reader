"""
What kinds of evidence exist, and which a given corpus can actually reach.

The tier numbers, their binding labels, their confidence levels and the
evidence each depends on were spread across `bind.py` as literals: a dict
mapping tier to (binding, confidence) in one place, a `TIER_NAMES` dict in
another, `for t in (0, 1, 2, 3, 4, 5)` in the report, and ten scattered
`tiers[i] = <int>` assignments. Adding Tier 0 meant editing four of those and
hoping. They are one table now.

The second thing this file does is make "which tiers can this corpus reach" a
COMPUTED property rather than an assumption. al-Tajrid has a workbook and a
vocalised parent edition and can reach all six. The Muwatta' has a parent
edition and no workbook, so Tiers 1, 3 and 4 are not merely empty for it --
they are unavailable, which is a different statement and must read differently
in the report. A corpus with neither can only ever be Tier 0 or Tier 5.

WHY THIS IS A TABLE AND NOT A CLASS HIERARCHY
---------------------------------------------
The obvious next step is a Resolver per tier with a `propose()` method, chained
in order. That would be wrong here, and it is worth writing down why before
someone tries it:

  * Tier 2's alignment MINTS lexicon entries (`mint_from_witness`) that Tiers 1
    and 4 then read. The strategies share mutable state by design.
  * The collocation table that Tier 3 votes with is built FROM the output of
    Tiers 1 and 2, across every record, after both have run.
  * The consistency repair REWRITES a Tier 2 binding into a Tier 3 one when the
    alignment was positionally undetermined.

So the tiers are not independent strategies over one token. They are stages of
a pipeline over the whole corpus, and two of them are inherently cross-record.
Modelling them as interchangeable per-token resolvers would either lose those
couplings or smuggle them back in as hidden ordering constraints -- and the
measured 97.0% gate depends on every one of them.

What IS per-token and independent: Tier 0 (read the source), Tier 1 (count the
candidates), Tier 3-case, Tier 4 (most frequent). Those are the ones worth
extracting if this file grows further. The alignment and the repair are not.
"""

from __future__ import annotations

from dataclasses import dataclass


# Evidence a corpus may or may not possess. Names match the `sources` keys in
# `corpora/{id}.yaml` where they correspond to a file.
LEXICON = "lexicon"
WITNESS = "vocalisation_reference"
SOURCE_MARKS = "source_vocalisation"   # not a file: a property of the text

# Derived, not declared. Tiers 1, 3 and 4 do not need a WORKBOOK -- they need an
# INVENTORY of candidate readings to choose among. A workbook is one way to get
# one; minting from an aligned witness is another, and the Muwatta' run proved
# it: with no workbook at all, Tier 1 still bound 40.8% of matn tokens off
# entries the aligner had minted moments earlier.
#
# Declaring `requires={LEXICON}` for those tiers printed "Tier 1 unavailable"
# directly above a line reporting 59,829 Tier 1 tokens. The evidence model was
# wrong, and the first real witness-only corpus said so.
INVENTORY = "inventory"
GLOSSES = "glosses"


@dataclass(frozen=True)
class Tier:
    n: int
    binding: str          # the `Binding` literal in contracts.py
    confidence: str
    label: str            # for the report table
    requires: frozenset   # evidence without which this tier cannot fire
    witnessed: bool       # counts toward the coverage gate
    note: str


TIERS: tuple[Tier, ...] = (
    Tier(0, "source", "high", "0 source-vowelled", frozenset({SOURCE_MARKS}), True,
         "The corpus file printed the vowelling itself. Nothing was inferred."),
    Tier(1, "unique", "high", "1 unique", frozenset({INVENTORY}), True,
         "Exactly one lexicon entry matches the spelling."),
    # DECIDED at Phase 4: {WITNESS} alone. The aligner mints an entry for any
    # matched position when there is no workbook to supply an inventory, so a
    # witness-only corpus reaches Tier 2 rather than bottoming out at Tier 5.
    # What it does NOT get is glosses: the workbook is the only gloss source,
    # and an entry minted from the witness carries vowelling and whatever
    # morphology the analyser recovered, and nothing else.
    Tier(2, "aligned", "high", "2 aligned", frozenset({WITNESS}), True,
         "Transferred from the aligned word in a vocalised parent edition."),
    Tier(3, "heuristic", "medium", "3 heuristic (case)", frozenset({INVENTORY}), False,
         "Inferred from syntax or from the same collocation elsewhere."),
    Tier(4, "heuristic", "low", "4 heuristic (most-frequent)", frozenset({INVENTORY}), False,
         "The most frequent candidate. A guess, and labelled one."),
    Tier(5, "unbound", "none", "5 unbound", frozenset(), False,
         "No lexicon entry. Not clickable."),
)

BY_N = {t.n: t for t in TIERS}


def resources_for(cfg: dict, *, source_has_marks: bool = False) -> frozenset:
    """
    Which kinds of evidence this corpus actually has.

    `source_has_marks` is passed in rather than read from the config because it
    is a measured property of the fetched text, not a declaration. A corpus
    cannot be trusted to know whether its own file is vowelled -- 179 sampled
    OpenITI texts carry no marks at all, and the two configured here are bare,
    so anything asserting otherwise in a yaml would be a guess.
    """
    sources = cfg.get("sources") or {}
    have = set()
    if sources.get(LEXICON):
        have.update({LEXICON, INVENTORY, GLOSSES})
    if sources.get(WITNESS):
        # An inventory too, via minting -- but never glosses. The workbook is
        # the only gloss source there is.
        have.update({WITNESS, INVENTORY})
    if source_has_marks:
        have.add(SOURCE_MARKS)
    return frozenset(have)


def available(resources: frozenset) -> tuple[Tier, ...]:
    """The tiers this corpus can reach. Tier 5 always can."""
    return tuple(t for t in TIERS if t.requires <= resources)


def unavailable(resources: frozenset) -> tuple[Tier, ...]:
    return tuple(t for t in TIERS if not (t.requires <= resources))


def explain(resources: frozenset) -> list[str]:
    """
    Report lines saying what this corpus can and cannot reach, and why.

    A tier that is unavailable must not be printed as 0.0% beside tiers that
    are merely empty: one means "measured, none found", the other means "never
    consulted". Conflating them is how a witness-only corpus would look like a
    failing corpus.
    """
    out: list[str] = []
    missing = unavailable(resources)
    if not missing:
        return out
    out.append("Tiers unavailable to this corpus (NOT measured as zero):")
    for t in missing:
        lacks = ", ".join(sorted(t.requires - resources))
        out.append(f"  Tier {t.n} {t.label:<28} needs {lacks}")
    return out
