#!/usr/bin/env python3
"""
Bind every corpus token to a lexicon entry. Phase 3, Path B.

    python pipeline/bind.py              # bind + report
    python pipeline/bind.py --sample 100 # also emit the stratified audit sample

Five tiers, each measured separately, because the point is not to bind
everything but to be honest about how each binding was arrived at:

  1 unique     search_key resolves to exactly one surface form. Free, correct.
  2 aligned    resolved against fully-diacritised Bukhari by sequence alignment.
  3 heuristic  resolved by case/mood agreement with a governing particle.
  4 heuristic  most-frequent candidate. A guess, and labelled low confidence.
  5 unbound    no lexicon entry at all. Not clickable.

On finding the Bukhari counterpart: the CSV is NOT indexed by hadith number.
It has 7,008 rows while al-Tajrid's own `(بخاري: N)` references run to 7,563,
and testing every offset from -2 to +2 gives a flat ~24% token overlap with no
peak — i.e. the row order does not track the standard numbering at all. So the
counterpart is RETRIEVED by content: an IDF-weighted inverted index over rare
tokens, which finds a row whose median token overlap with the Tajrid hadith is
0.96. The `(بخاري: N)` reference is then used to corroborate, not to look up.
"""

from __future__ import annotations

import argparse
import collections
import difflib
import json
import math
import random
import re

import yaml
import sys
from pathlib import Path

import pandas as pd

from corpus import ConfigError, inline_strip_patterns, load_config, source_path
from glossary import CARRY as GLOSSARY_FIELDS
from tiers import (TIERS, BY_N as TIER_BY_N, GLOSSES, available, explain,
                   resources_for)
from vocalisation import FULL, NONE, PARTIAL, agrees, classify, is_consistent
from lexicon import stable_id
from normalise import dediac, normalise
from tokenise import tokenise

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "build"   # scoped per corpus at runtime: OUT / corpus
REPORTS = ROOT / "reports"

ARABIC = re.compile(r"[\u0621-\u064a]")
STRIP_EDGE = re.compile(r"^[^\u0621-\u064a]+|[^\u0621-\u064a\u064b-\u0652\u0670]+$")


HARAKAT = "\u064e\u064f\u0650\u064b\u064c\u064d"  # a u i, and their tanwin
KASRA, DAMMA, FATHA = "\u0650", "\u064f", "\u064e"
KASRATAN, DAMMATAN, FATHATAN = "\u064d", "\u064c", "\u064b"

# Tier 3 governors. Kept deliberately small and explainable — a rule a student
# could check beats a model nobody can audit.
GENITIVE_TRIGGERS = {
    normalise(w) for w in
    "من في على عن إلى الى مع عند بين لدى حتى منذ خلال قبل بعد فوق تحت دون سوى نحو".split()
}
ACCUSATIVE_TRIGGERS = {normalise(w) for w in "إن أن كأن لكن لعل ليت إنما".split()}

RETRIEVAL_DF_CEILING = 400   # ignore tokens appearing in more rows than this
MIN_COVERAGE = 0.35          # below this the retrieved row is not the counterpart
ANCHOR_BLOCK = 2             # matching blocks this short do not pin down position
WITNESS_BLOCK = 3            # blocks this long are trusted to correct the lexicon

# Nouns governed by these are majrur. al-Tajrid rewrites Bukhari's isnad
# openings — `سمعت عمرَ بنَ الخطاب` becomes `عن عمرَ بنِ الخطاب` — which CHANGES
# THE CASE. Alignment transfers Bukhari's vowelling verbatim and so imports the
# wrong ending. Measured: 194 of 491 `عن <name> بن` openings were wrong.
IBN_FORMS = {"بن", "ابن", "بنت"}
REPAIR_MIN_SUPPORT = 20      # evidence needed to overrule an alignment
REPAIR_MIN_PURITY = 0.90


def final_haraka(vocalised: str) -> str | None:
    """The last short vowel or tanwin in a form — its case/mood marker."""
    for ch in reversed(vocalised):
        if ch in HARAKAT:
            return ch
    return None


def _is_lexicon_guess(voc_source) -> bool:
    """
    Did the workbook WITNESS this vowelling, or fall back to its commonest?

    `voc_source` reads like `aligned:4508,lexicon_mfv:74`. Where the fallback
    outweighs the aligned evidence, the form's vowelling is the workbook's own
    guess — and a form with exactly one such candidate is not "unambiguous", it
    is unopposed. الْأَعْمَالِ was one of these: four occurrences, three of them
    from the fallback, and the reader was told the reading was not in doubt.
    """
    if not isinstance(voc_source, str):
        return False
    counts: dict[str, int] = {}
    for part in voc_source.split(","):
        if ":" in part:
            name, _, n = part.rpartition(":")
            try:
                counts[name.strip()] = int(n)
            except ValueError:
                pass
    fallback = sum(v for k, v in counts.items() if k.startswith("lexicon_mfv"))
    witnessed = sum(v for k, v in counts.items() if k.startswith("aligned"))
    return fallback > witnessed


class Lexicon:
    def __init__(self, curated: "list[dict] | None" = None,
                 review: "tuple[set[str], dict[str, set[str]]] | None" = None) -> None:
        """
        The inventory of candidate readings, however it was obtained.

        `curated` is a list of plain row dicts -- NOT a file, and not a
        spreadsheet. al-Tajrid supplies them from its workbook via
        `workbook.read_surface`; every later corpus supplies nothing here and
        fills the inventory from its witness instead (`seed_from_witness`).
        This class deliberately cannot tell the difference, which is what keeps
        one text's exceptional input out of everyone else's path.

        `curated is None` builds an EMPTY lexicon that can still be minted
        into. That is not a degenerate case to be tolerated; it is the normal
        shape from the second corpus onward.
        """
        self.by_key: dict[str, list[str]] = collections.defaultdict(list)
        self.entry: dict[str, dict] = {}
        self.by_key_form: dict[tuple[str, str], str] = {}
        self.minted: set[str] = set()
        self.review: set[str] = set()
        self.plausible: dict[str, set[str]] = {}
        analyses_path = OUT / "morphology" / "analyses.json"
        self.analyses: dict = (
            json.loads(analyses_path.read_text(encoding="utf-8"))
            if analyses_path.exists() else {}
        )
        # An absent cache is survivable for a CURATED corpus -- al-Tajrid's
        # rows already carry lemma, root and POS, and the analyser only fills
        # gaps. For a derived corpus it is the sole source of morphology, and
        # its absence means every minted entry gets vowelling and nothing else.
        self.have_analyses = bool(self.analyses)

        # Was this inventory CURATED for this text, or derived from a witness?
        # Three behaviours turn on it, and none of them care that the curation
        # arrived as a spreadsheet:
        #   - mint on any matched position, or only on a long block
        #   - treat a short block as positionally undetermined by default
        #   - whether "only one candidate" means "settled" or merely
        #     "only one reading was ever witnessed"
        self.curated = curated is not None
        if curated is None:
            return

        for r in curated:
            key, voc = r["search_key"], r["vocalized"]
            # Identifiers must match lexicon.py's stable scheme exactly, so the
            # derivation lives in one place and is imported, not re-implemented.
            mid = stable_id(key, voc)
            self.by_key[key].append(mid)
            self.entry[mid] = {
                "vocalized": voc, "freq": r["freq"], "pos": r["pos"],
                "unvocalized": r["unvocalized"], "search_key": key,
                # How the curation arrived at each vowelling. Tiering never read
                # this, which is how a guess came to be labelled "not in doubt".
                "lexiconGuess": _is_lexicon_guess(r.get("voc_source")),
            }
            self.by_key_form.setdefault((key, voc), mid)

        if review is not None:
            self.review, self.plausible = review

    def seed_from_witness(self, witness: "WitnessIndex") -> int:
        """
        Build the candidate inventory from the witness's whole VOCABULARY,
        not just from the row a record aligns to.

        This is the workbook's structural job, and it turns out to be
        derivable. Measured on al-Tajrid with the workbook removed: 16.8% of
        matn tokens fell to Tier 5, and 98.0% of them were words that DO occur
        in the vocalised Bukhari -- somewhere else. They were unbound only
        because record-level retrieval never reached them: commentary
        paragraphs with no counterpart hadith, and the long tail generally
        (17,548 distinct keys for 19,987 tokens, almost all hapax).

        Aligning a record gives POSITION -- this reading, here, witnessed in
        context, which is Tier 2. Reading the witness as a type lexicon gives
        INVENTORY -- the set of vowellings this spelling is known to take,
        which is what Tiers 1, 3 and 4 choose among. The two are different
        questions and the second does not need a workbook to answer.

        Ordering matters: seeding must happen BEFORE binding, so that
        `candidates()` is populated when Tier 1 counts them.
        """
        before = len(self.entry)
        for row_keys, row_forms in zip(witness.norm, witness.forms):
            for key, form in zip(row_keys, row_forms):
                if key and form:
                    self.mint_from_witness(key, form)
        return len(self.entry) - before

    def enrich_from_glossary(self, path: Path) -> dict:
        """
        Fill meaning from the corpus-independent glossary.

        Same contract as `enrich_from`: it may say what a word MEANS, never
        which reading is right here. The glossary carries no frequency and no
        corpus statistics precisely so that it cannot.
        """
        doc = json.loads(path.read_text(encoding="utf-8"))
        label, entries = doc.get("source", "glossary"), doc["entries"]
        got = collections.Counter()
        for mid, row in entries.items():
            e = self.entry.get(mid)
            if e is None:
                continue
            for field, val in row.items():
                if field in ("match_id", "search_key", "vocalized"):
                    continue
                if e.get(field) in (None, "", "nan"):
                    e[field] = val
                    got[field] += 1
            e.setdefault("glossFrom", label)
        return dict(got)

    def enrich_from(self, donor_rows: list[dict], label: str) -> dict:
        """
        Fill missing gloss, lemma, root and POS from ANOTHER corpus's workbook.

        `match_id` is `stable_id(search_key, vocalized)` -- derived from the
        form, never from frequency -- so the same reading carries the same id in
        every corpus. ARCHITECTURE.md states that a lexical entry is
        corpus-independent; this is the first code that actually spends it.

        Enrichment only, deliberately. Donor rows do NOT enter the candidate
        set and do NOT vote in any tier: importing al-Tajrid's inventory into
        the Muwatta' would let one book's readings decide another book's
        ambiguities, which is precisely the cross-corpus contamination Phase 1
        went to some trouble to make impossible. What transfers is what a word
        MEANS, which does not belong to a corpus. What does not transfer is
        which reading is right HERE.

        Frequency is likewise not imported: `freq` is a per-corpus statistic,
        which is why the payload keeps `lex/stats-*` separate from
        `lex/surface-*` in the first place.
        """
        got = collections.Counter()
        for r in donor_rows:
            key, voc = str(r["search_key"]), str(r["vocalized"])
            mid = stable_id(key, voc)
            e = self.entry.get(mid)
            if e is None:
                continue
            for field in ("gloss_msa", "lemma", "root", "pos", "unvocalized"):
                val = r.get(field)
                if val is None or str(val) == "nan" or str(val) == "":
                    continue
                if e.get(field) in (None, "", "nan"):
                    e[field] = str(val)
                    got[field] += 1
            e.setdefault("glossFrom", label)
        return dict(got)

    def mint_from_witness(self, key: str, vocalized: str) -> str | None:
        """
        Add a reading attested by the witness but absent from the workbook.

        The new entry carries vowelling, lemma, root and part of speech, and no
        gloss or frequency — the workbook is the only gloss source and it does
        not know this form. The interface must say so rather than show a blank.
        """
        existing = self.by_key_form.get((key, vocalized))
        if existing:
            return existing
        mid = stable_id(key, vocalized)
        analysis = self.analyses.get(vocalized) or {}
        self.entry[mid] = {
            "vocalized": vocalized,
            "freq": 0,
            "pos": analysis.get("pos"),
            # dediac, not the vocalised form. `unvocalized` keeps hamza and
            # alef distinctions and drops only the marks -- it is what the
            # Review sheet and the interface key on, and it is NOT search_key,
            # which folds those letters too. Minting used to store the fully
            # vowelled string here, so a minted entry and a curated entry for
            # the same match_id disagreed on a field that is supposed to be a
            # property of the form.
            "unvocalized": dediac(vocalized),
            "search_key": key,
            "lexiconGuess": False,
            "fromWitness": True,
            "lemma": analysis.get("lemma"),
            "root": analysis.get("root"),
        }
        self.by_key_form[(key, vocalized)] = mid
        self.by_key.setdefault(key, []).append(mid)
        self.minted.add(mid)
        return mid

    def candidates(self, key: str) -> list[str]:
        return self.by_key.get(key, [])

    def most_frequent_plausible(self, cands: list[str], raw: str) -> str:
        """
        The commonest candidate the reference corpus also attests.

        `cands` is already sorted by frequency in THIS corpus, so this only
        moves the answer when our most frequent reading is one the reference
        corpus never records for the form as written.

        The lookup MUST be keyed on the token as it appears in the text. The
        Review sheet is keyed by undiacritised surface form, and within one
        search_key several entries can have different undiacritised forms —
        normalise() folds hamza and ta marbuta, Review does not. Keying on the
        top candidate instead silently looked up a different word and the rule
        did nothing.
        """
        if not cands:
            return ""
        allowed = self.plausible.get(raw)
        if not allowed:
            return cands[0]
        for mid in cands:
            if self.entry[mid]["vocalized"] in allowed:
                return mid
        return cands[0]


class WitnessIndex:
    """Content retrieval over a fully-diacritised witness edition."""

    @staticmethod
    def _read(path: Path) -> list[str]:
        """
        One vocalised unit per row, from CSV or JSON.

        The Bukhari and Muwatta' witnesses are single-column CSVs. The
        sunnah.com-derived datasets are JSON with a `hadiths` array. Both are
        just a list of strings once read, and the index does not care which it
        came from — so the format lives here and nowhere else.
        """
        if path.suffix.lower() == ".json":
            doc = json.loads(path.read_text(encoding="utf-8"))
            items = doc["hadiths"] if isinstance(doc, dict) else doc
            return [str(h["arabic"]) for h in items if h.get("arabic")]
        return pd.read_csv(path).iloc[:, 0].astype(str).tolist()

    def __init__(self, path: Path) -> None:
        rows = self._read(path)
        self.forms = [
            [STRIP_EDGE.sub("", t) for t in s.split() if ARABIC.search(t)] for s in rows
        ]
        self.norm = [[normalise(t) for t in row] for row in self.forms]
        df = collections.Counter()
        for row in self.norm:
            df.update(set(row))
        n = len(self.norm)
        self.idf = {w: math.log(n / c) for w, c in df.items()}
        self.postings: dict[str, list[int]] = collections.defaultdict(list)
        for i, row in enumerate(self.norm):
            for w in set(row):
                if df[w] <= RETRIEVAL_DF_CEILING:
                    self.postings[w].append(i)

    def retrieve(self, query: list[str]) -> tuple[int | None, float]:
        scores: dict[int, float] = collections.defaultdict(float)
        # `sorted`, not bare `set`. Set iteration order over strings depends on
        # PYTHONHASHSEED, and float `+=` is not associative, so the same query
        # summed in a different order lands on a different value in the last
        # bits. Where two rows are within that margin the winner flips, and the
        # whole record aligns to a different hadith.
        #
        # This was not hypothetical: two runs of identical code produced four
        # differing tokens in matn-02224, which made regression testing against
        # a baseline impossible and quietly undermined every gate figure --
        # a number you cannot reproduce is not a measurement.
        for w in sorted(set(query)):
            for i in self.postings.get(w, ()):
                scores[i] += self.idf[w]
        if not scores:
            return None, 0.0
        # Explicit tie-break on the row index. Without it `max` returns the
        # first key in insertion order, which depends on the loop above.
        row = max(scores, key=lambda k: (scores[k], -k))
        q = set(query)
        coverage = len(q & set(self.norm[row])) / len(q) if q else 0.0
        return row, coverage


def tier3_case(cands: list[str], lex: Lexicon, prev_key: str | None) -> str | None:
    """
    Case agreement with a governing particle.

    A noun after a preposition is genitive; a noun after inna and its sisters is
    accusative. Where that narrows the candidates to exactly one, take it.
    Deliberately conservative: it fires only on an unambiguous single survivor.
    """
    if prev_key is None:
        return None
    if prev_key in GENITIVE_TRIGGERS:
        wanted = {KASRA, KASRATAN}
    elif prev_key in ACCUSATIVE_TRIGGERS:
        wanted = {FATHA, FATHATAN}
    else:
        return None
    survivors = [m for m in cands if final_haraka(lex.entry[m]["vocalized"]) in wanted]
    return survivors[0] if len(survivors) == 1 else None


COLLOCATION_MIN_SUPPORT = 4
COLLOCATION_MIN_PURITY = 0.90


def tier3_collocation(
    key: str, prev_key: str | None, next_key: str | None, table: dict
) -> tuple[str, str] | None:
    """
    Bind by agreement with the same collocation elsewhere in the corpus.

    Every token resolved by Tier 1 or Tier 2 votes for its (previous, current)
    and (current, next) bigrams. A still-ambiguous token whose bigram has at
    least COLLOCATION_MIN_SUPPORT observations that agree at least
    COLLOCATION_MIN_PURITY of the time inherits that reading.

    This is what rescues the honorific formulae. `رضي الله عنه` is nominative
    and `رسول الله` is genitive, categorically so in Bukhari — but where the
    alignment happens not to cover an instance, the most-frequent fallback gets
    it wrong, and it gets it wrong the same way every time. Evidence from
    thousands of aligned instances of the identical phrase is both stronger and
    more explainable than a corpus-wide frequency prior.
    """
    for bigram in (("L", prev_key, key), ("R", key, next_key)):
        if bigram[1] is None or bigram[2] is None:
            continue
        votes = table.get(bigram)
        if not votes:
            continue
        total = sum(votes.values())
        best, n = max(votes.items(), key=lambda kv: kv[1])
        if total >= COLLOCATION_MIN_SUPPORT and n / total >= COLLOCATION_MIN_PURITY:
            return best, f"{bigram[0]}-collocation {n}/{total}"
    return None


def load_corrections(corpus: str) -> tuple[dict, dict]:
    """
    Hand corrections, applied after every derived source.

    Precedence exists so a reader's judgement is not overwritten by the next
    rebuild. Everything else in this file is measured and fallible; this is the
    one input that is neither, and it wins.
    """
    path = ROOT / "corrections" / f"{corpus}.yaml"
    if not path.exists():
        return {}, {}
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    by_token = {
        (str(e["record"]), int(e["token"])): e for e in (doc.get("by_token") or [])
    }
    by_form = {}
    for e in doc.get("by_form") or []:
        by_form.setdefault(str(e["search_key"]), []).append(e)
    return by_token, by_form


def bind_corpus(
    records: list[dict],
    lex: Lexicon,
    witness_idx: WitnessIndex | None,
    corrections: tuple[dict, dict] = ({}, {}),
    strip: tuple[re.Pattern[str], ...] = (),
) -> tuple[dict, dict]:
    bound: dict[str, dict] = {}
    tally = collections.Counter()
    tally_matn = collections.Counter()
    reasons = collections.Counter()
    retrieval = {"attempted": 0, "no_row": 0, "low_coverage": 0, "coverages": []}
    ref_agree = {"checked": 0, "consistent": 0}
    undetermined: set[tuple[str, int]] = set()
    repairs = collections.Counter()
    syntax_fixes: collections.Counter = collections.Counter()
    unopposed = 0
    corrected: set[tuple[str, int]] = set()
    corr_token, corr_form = corrections
    witness_fixes: collections.Counter = collections.Counter()
    surfaces: dict[tuple[str, int], str] = {}
    source_voc = collections.Counter()
    witness_disagrees = collections.Counter()
    state: list[tuple[dict, str, list[dict], list[str], list[int | None], list[str | None]]] = []

    # ===== Pass 1: Tiers 1, 2, 5 =============================================
    for rec in records:
        leading, tokens = tokenise(rec["textRaw"], strip)
        keys = [normalise(t["raw"]) for t in tokens]
        tiers: list[int | None] = [None] * len(tokens)
        mids: list[str | None] = [None] * len(tokens)

        # ---- Tier 0: the source vowelled it itself -------------------------
        # Outranks the witness and the workbook, both of which are inferences
        # about a text that is right here saying what it means. Every corpus
        # configured today is bare, so this costs nothing and fires never --
        # until a text arrives from Shamela, Tanzil or a hadith dataset rather
        # than from OpenITI, at which point it is the difference between using
        # the best evidence available and discarding it.
        for i, tok in enumerate(tokens):
            state_of = classify(tok["raw"])
            source_voc[state_of] += 1
            if state_of != FULL:
                continue
            tiers[i] = 0
            mids[i] = lex.mint_from_witness(keys[i], tok["raw"])
            surfaces[(rec["id"], i)] = tok["raw"]

        for i, key in enumerate(keys):
            if tiers[i] is not None:
                continue
            cands = lex.candidates(key)
            # A PARTIALLY marked token cannot choose its own reading, but it
            # can rule readings out: a candidate must not contradict a mark the
            # source actually supplied. This is what stops partial vocalisation
            # -- the normal state of a Shamela text, which vowels Qur'anic
            # quotation and verse and leaves prose alone -- from being either
            # trusted wholesale or thrown away.
            raw = tokens[i]["raw"]
            if cands and classify(raw) == PARTIAL:
                narrowed = [m for m in cands if is_consistent(raw, lex.entry[m]["vocalized"])]
                if narrowed and len(narrowed) < len(cands):
                    reasons["partial-source narrowed candidates"] += len(cands) - len(narrowed)
                    cands = narrowed
            if not cands:
                tiers[i] = 5
            elif len(cands) == 1:
                tiers[i], mids[i] = 1, cands[0]

        if witness_idx is not None and rec["layer"] in ("matn", "zawaid") and keys:
            retrieval["attempted"] += 1
            row, coverage = witness_idx.retrieve(keys)
            if row is None:
                retrieval["no_row"] += 1
            elif coverage < MIN_COVERAGE:
                retrieval["low_coverage"] += 1
            else:
                retrieval["coverages"].append(coverage)
                # Which keys appear in this Bukhari row with more than one
                # vocalisation? For those, a short matching block does not
                # actually pin down WHICH occurrence we aligned to.
                row_forms: dict[str, set[str]] = collections.defaultdict(set)
                for k, f in zip(witness_idx.norm[row], witness_idx.forms[row]):
                    row_forms[k].add(f)
                sm = difflib.SequenceMatcher(None, keys, witness_idx.norm[row], autojunk=False)
                # A gap-filling pass was tried here and removed: difflib returns
                # MAXIMAL blocks under a longest common subsequence, so a word
                # unique in both gaps would already be matched — matching it
                # extends the subsequence. It produced exactly zero fills. The
                # 1,670 unmatched-but-present tokens are REORDERINGS, and
                # matching those means allowing crossing alignments, which
                # abandons the positional determinacy that makes Tier 2 worth
                # calling high confidence.
                for a, b, size in sm.get_matching_blocks():
                    for d in range(size):
                        i = a + d
                        witness = witness_idx.forms[row][b + d]

                        # The witness may attest a reading the workbook's
                        # inventory lacks — طَائِفَةٌ where it has only
                        # طَائِفَةً and طَائِفَةٍ. Mint the entry rather than
                        # discard the evidence: 1,031 tokens, 1,019 of them in
                        # positionally trusted blocks. Without this the token
                        # falls back to a wrong single option, which is exactly
                        # how إِنَّمَا الْأَعْمَالِ happened.
                        # WITNESS_BLOCK guards against minting off a short,
                        # positionally uncertain match — sound when a workbook
                        # already supplies the inventory and the witness is
                        # only filling gaps in it.
                        #
                        # With NO workbook the same rule leaves the corpus with
                        # no inventory at all, and every token unbound. There
                        # the alignment is not an addition to the evidence, it
                        # is the evidence, so mint on any matched position and
                        # let the block length govern CONFIDENCE instead.
                        if size >= WITNESS_BLOCK or not lex.curated:
                            lex.mint_from_witness(keys[i], witness)

                        # Tier 0 is never overwritten -- but a witness that
                        # disagrees with a vowelled source is a fact about the
                        # two EDITIONS, and worth counting rather than hiding.
                        if tiers[i] == 0:
                            if not agrees(tokens[i]["raw"], witness):
                                witness_disagrees[(tokens[i]["raw"], witness)] += 1
                            continue
                        if tiers[i] == 1 and size >= WITNESS_BLOCK:
                            # Tier 1 means the LEXICON had one option — not that
                            # the option is right. Where a positionally trusted
                            # alignment shows a different vowelling of the same
                            # word, the witness wins. The lexicon entry still
                            # applies: same lemma, same root, different ending.
                            # 585 tokens, including الْأَعْمَالِ in hadith 1,
                            # which must be الْأَعْمَالُ after إنما.
                            lex_form = lex.entry[mids[i]]["vocalized"] if mids[i] else None
                            if lex_form and witness != lex_form:
                                surfaces[(rec["id"], i)] = witness
                                witness_fixes[(lex_form, witness)] += 1
                            continue
                        if tiers[i] is not None:
                            continue
                        mid = lex.by_key_form.get((keys[i], witness))
                        if mid:
                            tiers[i], mids[i] = 2, mid
                            if size <= ANCHOR_BLOCK and len(row_forms[keys[i]]) > 1:
                                undetermined.add((rec["id"], i))
                            elif size <= ANCHOR_BLOCK and not lex.curated:
                                # No workbook means no second opinion on whether
                                # this position was pinned down. Short blocks
                                # are undetermined by default rather than by
                                # evidence of ambiguity.
                                undetermined.add((rec["id"], i))
                if rec["crossRefs"]:
                    ref_agree["checked"] += 1
                    if row + 1 in rec["crossRefs"] or coverage >= 0.8:
                        ref_agree["consistent"] += 1

        # ---- syntactic override -------------------------------------------
        # A hard rule about OUR text's syntax beats a witness to a DIFFERENT
        # text's syntax. `بن` between two names inherits the case of the name it
        # follows, and after a preposition that name is majrur.
        for i, key in enumerate(keys):
            if key not in IBN_FORMS or i < 2:
                continue
            if keys[i - 2] not in GENITIVE_TRIGGERS:
                continue
            wanted = [
                m for m in lex.candidates(key)
                if final_haraka(lex.entry[m]["vocalized"]) in {KASRA, KASRATAN}
            ]
            if len(wanted) == 1 and mids[i] != wanted[0]:
                mids[i] = wanted[0]
                tiers[i] = 3
                syntax_fixes[key] += 1

        state.append((rec, leading, tokens, keys, tiers, mids))

    # ===== Collocation evidence, from confidently-bound tokens only ==========
    table: dict[tuple[str, str, str], collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    # Positionally undetermined alignments are excluded from the evidence: they
    # are exactly the bindings most likely to be wrong, and letting them vote
    # would let a systematic alignment error certify itself.
    for rec, _, _, keys, tiers, mids in state:
        for i, mid in enumerate(mids):
            if tiers[i] not in (1, 2) or mid is None:
                continue
            if (rec["id"], i) in undetermined:
                continue
            if i:
                table[("L", keys[i - 1], keys[i])][mid] += 1
            if i + 1 < len(keys):
                table[("R", keys[i], keys[i + 1])][mid] += 1

    # ===== Consistency repair ================================================
    # A Tier-2 binding is normally the strongest evidence we have: an actual
    # vocalised witness at the aligned position. But when the same word occurs
    # several times in the Bukhari hadith with different case endings, and our
    # matching block was too short to say which occurrence we hit, the aligner
    # can transfer the wrong one. `رسول الله` is genitive and `رضي الله` is
    # nominative — categorically so in Bukhari — yet a mis-anchored match will
    # swap them. Where such an undetermined binding contradicts overwhelming
    # evidence from the same collocation elsewhere, prefer the evidence and
    # demote the token to medium confidence, because the alignment did not in
    # fact determine it.
    for rec, _, _, keys, tiers, mids in state:
        for i in range(len(keys)):
            if tiers[i] != 2 or (rec["id"], i) not in undetermined:
                continue
            prev_key = keys[i - 1] if i else None
            next_key = keys[i + 1] if i + 1 < len(keys) else None
            for bigram in (("L", prev_key, keys[i]), ("R", keys[i], next_key)):
                if bigram[1] is None or bigram[2] is None:
                    continue
                votes = table.get(bigram)
                if not votes:
                    continue
                total = sum(votes.values())
                best, n = max(votes.items(), key=lambda kv: kv[1])
                if (total >= REPAIR_MIN_SUPPORT and n / total >= REPAIR_MIN_PURITY
                        and best != mids[i]):
                    mids[i], tiers[i] = best, 3
                    repairs[f"{bigram[0]}-repair"] += 1
                    break

    # ===== Pass 2: Tiers 3 and 4 =============================================
    for rec, leading, tokens, keys, tiers, mids in state:
        for i, key in enumerate(keys):
            if tiers[i] is not None:
                continue
            cands = lex.candidates(key)
            prev_key = keys[i - 1] if i else None
            next_key = keys[i + 1] if i + 1 < len(keys) else None

            hit = tier3_collocation(key, prev_key, next_key, table)
            if hit:
                tiers[i], mids[i] = 3, hit[0]
                reasons[hit[1].split()[0]] += 1
                continue
            pick = tier3_case(cands, lex, prev_key)
            if pick:
                tiers[i], mids[i] = 3, pick
                reasons["case-agreement"] += 1
                continue
            # Tier 4: the most frequent candidate, restricted to readings the
            # Review sheet considers plausible where it has an opinion.
            tiers[i], mids[i] = 4, lex.most_frequent_plausible(cands, tokens[i]["raw"])

        out = []
        for i, tok in enumerate(tokens):
            tier, mid = tiers[i], mids[i]
            # Corrections last, so they beat witness, analyser and lexicon
            # alike. A corrected reading is not a guess and is not labelled one.
            fix = corr_token.get((rec["id"], i))
            if fix is None:
                for cand in corr_form.get(keys[i], []):
                    prev = tokens[i - 1]["raw"] if i else None
                    if "after" not in cand or cand["after"] == prev:
                        fix = cand
                        break
            if fix is not None:
                minted_id = lex.mint_from_witness(keys[i], str(fix["surface"]))
                if minted_id:
                    tiers[i], mids[i] = 1, minted_id
                    corrected.add((rec["id"], i))

            binding, confidence = TIER_BY_N[tier].binding, TIER_BY_N[tier].confidence
            # Tier 1 means the LEXICON offered one candidate — not that the
            # candidate is right. Where that candidate's own vowelling was the
            # workbook's fallback rather than a witness, the reading is not
            # certain and must not be labelled as if it were. The TIER is
            # unchanged, so coverage accounting and the 90% gate stay
            # comparable; only the honesty of the label moves.
            if tier == 1 and mid and lex.entry[mid]["lexiconGuess"]:
                confidence = "medium"
                unopposed += 1
            # On a minted-only inventory, "unique" means only that ONE reading
            # was ever witnessed -- not that a curated lexicon holds one entry.
            # Nothing has ranked the alternatives because nothing knows what
            # the alternatives are. Same failure the workbook's own fallback
            # had, so it gets the same label.
            elif tier == 1 and mid and not lex.curated:
                confidence = "medium"
                unopposed += 1
            out.append({
                "i": i,
                "surface": surfaces.get(
                    (rec["id"], i),
                    lex.entry[mid]["vocalized"] if mid else tok["raw"],
                ),
                "raw": tok["raw"],
                "matchId": mid,
                "binding": binding,
                "confidence": confidence,
                "clickable": mid is not None,
                "punctuationAfter": tok["punctuationAfter"],
                "tier": tier,
            })
            tally[tier] += 1
            if rec["layer"] == "matn":
                tally_matn[tier] += 1
        bound[rec["id"]] = {"leading": leading, "tokens": out}

    reasons.update(repairs)
    reasons["Tier 1 unopposed but unwitnessed"] = unopposed
    reasons["hand corrections applied"] = len(corrected)
    reasons["Tier 0 from source vowelling"] = source_voc.get(FULL, 0)
    reasons["syntax-override (ibn)"] = sum(syntax_fixes.values())
    reasons["witness-corrected Tier 1"] = sum(witness_fixes.values())
    return bound, {"tally": tally, "tally_matn": tally_matn, "reasons": reasons,
                   "retrieval": retrieval, "refAgree": ref_agree,
                   "sourceVocalisation": dict(source_voc),
                   "witnessDisagrees": witness_disagrees}


def derive_lexicon(bound: dict, records: list[dict], lex: Lexicon) -> dict:
    """
    Build `lexicon.json` for a corpus that has no frequency workbook.

    Normally `lexicon.py` produces this from the workbook and runs BEFORE
    binding. A minted corpus inverts that: the inventory does not exist until
    the alignment has run, so the lexicon is derived here, afterwards.

    The useful realisation is how little of the workbook is structural.
    `freq`, `rank`, `pct`, `cum_pct`, `doc_freq`, `layers` and `first_record`
    are COUNTS OVER THIS CORPUS and are recomputed here exactly as the workbook
    measured them. What cannot be derived is the lexicography -- gloss,
    divergence, technical senses, curated names -- which is what a workbook
    exists to supply, and what `lexicon_donors` fills in from a sibling.

    So the workbook is not a structural dependency. It is a source of meaning.
    """
    layer_of = {r["id"]: r["layer"] for r in records}
    freq = collections.Counter()
    docs: dict[str, set] = collections.defaultdict(set)
    layers: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    first: dict[str, str] = {}
    for rid, rec in bound.items():
        for t in rec["tokens"]:
            mid = t["matchId"]
            if not mid:
                continue
            freq[mid] += 1
            docs[mid].add(rid)
            layers[mid][layer_of.get(rid, "matn")] += 1
            first.setdefault(mid, rid)

    total = sum(freq.values()) or 1
    surface: dict[str, dict] = {}
    cum = 0
    for rank, (mid, n) in enumerate(freq.most_common(), 1):
        e = lex.entry[mid]
        cum += n
        surface[mid] = {
            "match_id": mid,
            "search_key": e["search_key"],
            "vocalized": e["vocalized"],
            "unvocalized": e.get("unvocalized") or dediac(e["vocalized"]),
            "freq": n, "rank": rank,
            "pct": round(100 * n / total, 6),
            "cum_pct": round(100 * cum / total, 6),
            "doc_freq": len(docs[mid]),
            "layers": dict(layers[mid]),
            "first_record": first[mid],
            "pos": e.get("pos"), "lemma": e.get("lemma"), "root": e.get("root"),
            "gloss_msa": e.get("gloss_msa"),
            # Everything else the glossary supplied. This was a fixed list that
            # happened to name gloss, lemma, root and POS -- so `lane_root`,
            # `classical_keywords`, `domain` and the rest were enriched onto the
            # entry and then dropped on the way out. The visible symptom was
            # that Lane's Lexicon appeared only in al-Tajrid: every other corpus
            # lost the root that links a word to its Lane entry.
            **{f: e[f] for f in GLOSSARY_FIELDS if e.get(f) not in (None, "", "nan")},
            # Provenance: the interface can distinguish a gloss written FOR
            # this book from one borrowed from a sibling corpus.
            "glossFrom": e.get("glossFrom"),
            "fromWitness": True,
            # Absent by construction, not merely empty.
            "divergence": None, "technical_sense": None,
            "voc_source": "minted:witness",
        }

    by_key: dict[str, list[str]] = collections.defaultdict(list)
    by_unvoc: dict[str, list[str]] = collections.defaultdict(list)
    lemmas: dict[str, list[str]] = collections.defaultdict(list)
    roots: dict[str, list[str]] = collections.defaultdict(list)
    for mid, row in surface.items():
        by_key[row["search_key"]].append(mid)
        by_unvoc[row["unvocalized"]].append(mid)
        if row["lemma"]:
            lemmas[str(row["lemma"])].append(mid)
        if row["root"]:
            roots[str(row["root"])].append(mid)

    return {"surface": surface, "searchKeyIndex": dict(by_key),
            "unvocalizedIndex": dict(by_unvoc), "lemmas": dict(lemmas),
            "roots": dict(roots), "names": {}, "technicalSenses": {},
            "divergence": {}, "review": {}}


TIER_NAMES = {t.n: t.label for t in TIERS}


def report(stats: dict, gates: dict | None = None,
           resources: frozenset | None = None) -> list[str]:
    L: list[str] = []
    tally, matn = stats["tally"], stats["tally_matn"]
    tot, totm = sum(tally.values()), sum(matn.values())
    L.append(f"{'tier':<32}{'all tokens':>12}{'%':>8}{'matn':>11}{'%':>8}")
    for t in sorted(TIER_BY_N):
        L.append(f"  {TIER_NAMES[t]:<30}{tally[t]:>12,}{100*tally[t]/tot:>7.1f}%"
                 f"{matn[t]:>11,}{100*matn[t]/totm:>7.1f}%")
    L.append(f"  {'TOTAL':<30}{tot:>12,}{100:>7.1f}%{totm:>11,}{100:>7.1f}%")
    # Tier 0 is witnessed by the source itself and counts with 1+2.
    # Which tiers count as witnessed is declared once, in tiers.py.
    witnessed = [t.n for t in TIERS if t.witnessed]
    t12 = 100 * sum(matn[n] for n in witnessed) / totm
    L.append("")
    # The threshold is PER CORPUS. A witness-only corpus cannot reach
    # al-Tajrid's 90%, and lowering a global constant to admit one would
    # quietly weaken al-Tajrid's own guarantee — the exact thing SPEC.md §8
    # exists to prevent. A corpus that declares no threshold is reported,
    # not gated, and says so.
    threshold = (gates or {}).get("min_witnessed_matn")
    if threshold is None:
        L.append(f"Tier 1+2 on matn: {t12:.1f}%  (no threshold declared — REPORTED, NOT GATED)")
    else:
        L.append(f"GATE — Tier 1+2 on matn: {t12:.1f}%  (requires >= {threshold:.1f}%)  "
                 f"{'PASS' if t12 >= threshold else 'FAIL'}")
    ceiling = (gates or {}).get("naive_ceiling_pct")
    if ceiling is not None:
        L.append(f"Naive ceiling for comparison: {ceiling}% "
                 "(always take the most frequent candidate)")
    if stats["reasons"]:
        L.append("")
        L.append("Tier 3 breakdown: " + ", ".join(
            f"{k} {v:,}" for k, v in stats["reasons"].most_common()))
    if resources is not None:
        lines = explain(resources)
        if lines:
            L.append("")
            L.extend(lines)

    morph = stats.get("morphology")
    if morph:
        L.append("")
        L.append("Morphology on bound matn tokens "
                 "(root drives the 'other forms of this root' navigation):")
        for field in ("lemma", "root", "pos"):
            # `.get`: a corpus with no donors and no analyses has ZERO of a
            # field, and a Counter drops absent keys on the way to a dict.
            got, tot = morph.get(field, 0), morph.get("bound", 0)
            L.append(f"  {field:<8}{got:>10,} / {tot:,}  {100*got/max(tot,1):>5.1f}%")
        if not morph.get("have_analyses"):
            L.append("  Source: DONORS ONLY — no analyses.json was present.")

    enr = stats.get("enrichment") or {}
    if enr:
        L.append("")
        L.append("Gloss enrichment from sibling corpora "
                 "(match_id is derived from the form, so an entry is shared):")
        for donor, fields in enr.items():
            L.append(f"  from {donor}: " + ", ".join(
                f"{k} {v:,}" for k, v in sorted(fields.items())) or f"  from {donor}: nothing")

    if resources is not None and GLOSSES not in resources and not enr:
        L.append("")
        L.append("NO GLOSSES. This corpus has no frequency workbook, so every entry was")
        L.append("  minted from the alignment: vowelling and morphology only. The reader")
        L.append("  can show how a word is pronounced and not what it means.")

    sv = stats.get("sourceVocalisation") or {}
    marked = sv.get("full", 0) + sv.get("partial", 0)
    if marked:
        total_sv = sum(sv.values()) or 1
        L.append("")
        L.append(f"Source vocalisation: {sv.get('full',0):,} tokens fully vowelled "
                 f"({100*sv.get('full',0)/total_sv:.1f}%), "
                 f"{sv.get('partial',0):,} partially ({100*sv.get('partial',0)/total_sv:.1f}%)")
        wd = stats.get("witnessDisagrees") or {}
        if wd:
            n = sum(wd.values())
            L.append(f"  Witness disagrees with a vowelled source on {n:,} tokens "
                     f"({len(wd):,} distinct pairs). The SOURCE wins; this counts")
            L.append("  the editions' disagreement, it does not resolve it.")
            for (raw, wit), c in wd.most_common(5):
                L.append(f"    {c:>5,}x  source {raw}  witness {wit}")
    else:
        L.append("")
        L.append("Source vocalisation: none — every vowel below is inferred.")

    r = stats["retrieval"]
    if r.get("skipped"):
        L.append("")
        L.append("Tier 2 SKIPPED — this corpus declares no `sources.vocalisation_reference`.")
        L.append("  Every reading below is the workbook's, with no independent witness.")
    if r["coverages"]:
        cov = sorted(r["coverages"])
        L.append("")
        L.append(f"Witness retrieval: {len(cov):,} of {r['attempted']:,} records matched, "
                 f"median coverage {cov[len(cov)//2]:.3f}, "
                 f"{r['low_coverage']} below {MIN_COVERAGE}, {r['no_row']} with no candidate row")
    ra = stats["refAgree"]
    if ra["checked"]:
        L.append(f"Retrieved row corroborated by the record's own (بخاري: N) reference "
                 f"or coverage>=0.8: {ra['consistent']:,}/{ra['checked']:,} "
                 f"({100*ra['consistent']/ra['checked']:.1f}%)")
    return L


def review_crosscheck(bound: dict, records: list[dict], lex: Lexicon) -> list[str]:
    """
    The workbook flags 3,349 forms whose vocalisation was a most-frequent
    fallback rather than context-aligned. If our tiering is calibrated, those
    should be scarce in Tiers 1-2 and dense in Tiers 3-5.
    """
    per_tier = collections.Counter()
    flagged_per_tier = collections.Counter()
    for rec in records:
        for tok in bound[rec["id"]]["tokens"]:
            per_tier[tok["tier"]] += 1
            if tok["raw"] in lex.review or tok["matchId"] and \
               lex.entry[tok["matchId"]]["unvocalized"] in lex.review:
                flagged_per_tier[tok["tier"]] += 1
    L = ["", f"{'tier':<32}{'tokens':>10}{'on Review list':>16}{'rate':>8}"]
    for t in sorted(TIER_BY_N):
        n, f = per_tier[t], flagged_per_tier[t]
        L.append(f"  {TIER_NAMES[t]:<30}{n:>10,}{f:>16,}{(100*f/n if n else 0):>7.1f}%")
    return L


def holdout_eval(bound: dict, lex: Lexicon, records: list[dict]) -> list[str]:
    """
    Measure Tier 3 and Tier 4 accuracy against held-out ground truth.

    Tokens bound at Tier 2 have an independent witness: the vocalisation of the
    aligned word in a properly-edited Bukhari text. So hide that answer, ask
    what Tier 3 and Tier 4 would have produced for the same token, and compare.
    The alignment is not infallible, so this is an estimate rather than a true
    error rate — but it is measured on 55k+ tokens instead of eyeballed on a
    handful, and it is the only ground truth this corpus offers.
    """
    by_id = {r["id"]: r for r in records}
    keys_of = {rid: [normalise(t["raw"]) for t in rec["tokens"]] for rid, rec in bound.items()}

    table: dict[tuple[str, str, str], collections.Counter] = collections.defaultdict(
        collections.Counter
    )
    for rid, rec in bound.items():
        keys = keys_of[rid]
        for i, tok in enumerate(rec["tokens"]):
            if tok["tier"] not in (1, 2) or not tok["matchId"]:
                continue
            if i:
                table[("L", keys[i - 1], keys[i])][tok["matchId"]] += 1
            if i + 1 < len(keys):
                table[("R", keys[i], keys[i + 1])][tok["matchId"]] += 1

    res = {3: [0, 0, 0], 4: [0, 0]}  # tier3: [fired, correct, n/a]; tier4: [n, correct]
    for rid, rec in bound.items():
        keys = keys_of[rid]
        if by_id[rid]["layer"] not in ("matn", "zawaid"):
            continue
        for i, tok in enumerate(rec["tokens"]):
            if tok["tier"] != 2 or not tok["matchId"]:
                continue
            truth = tok["matchId"]
            prev_key = keys[i - 1] if i else None
            next_key = keys[i + 1] if i + 1 < len(keys) else None

            # Remove this token's own votes so it cannot certify itself.
            removed = []
            for bigram in (("L", prev_key, keys[i]), ("R", keys[i], next_key)):
                if bigram[1] is not None and bigram[2] is not None and bigram in table:
                    table[bigram][truth] -= 1
                    removed.append(bigram)
            hit = tier3_collocation(keys[i], prev_key, next_key, table)
            if hit is None:
                hit_case = tier3_case(lex.candidates(keys[i]), lex, prev_key)
                hit = (hit_case, "case") if hit_case else None
            for bigram in removed:
                table[bigram][truth] += 1

            if hit:
                res[3][0] += 1
                res[3][1] += hit[0] == truth
            else:
                res[3][2] += 1
            # Must exercise the SAME rule the binder uses, or the published
            # accuracy describes a function nothing calls.
            cands = lex.candidates(keys[i])
            res[4][0] += 1
            res[4][1] += lex.most_frequent_plausible(cands, rec["tokens"][i]["raw"]) == truth

    f, c, na = res[3]
    n4, c4 = res[4]
    L = ["", "## Held-out accuracy of the heuristic tiers", "",
         "Tier-2 tokens have an independent witness (the vocalised parent edition).",
         "Hiding it and re-deriving the answer measures what Tiers 3 and 4 are worth.", ""]
    L.append(f"  evaluated on {n4:,} Tier-2 tokens in matn and zawa'id")
    L.append(f"  Tier 3 rule fired on          {f:,} ({100*f/n4:.1f}%), "
             f"correct {c:,} = {100*c/max(f,1):.1f}%   -> error {100-100*c/max(f,1):.1f}%")
    L.append(f"  Tier 3 declined to fire on    {na:,} ({100*na/n4:.1f}%) — these fall to Tier 4")
    L.append(f"  Tier 4 most-frequent fallback {n4:,}, correct {c4:,} = {100*c4/n4:.1f}%"
             f"   -> error {100-100*c4/n4:.1f}%")
    L.append("")
    L.append(f"  So the medium/low confidence split is real: the Tier 3 rules are "
             f"{(100*c/max(f,1)) - (100*c4/n4):.0f} points more accurate than the "
             f"fallback they replace.")
    return L


def ambiguous_review_crosscheck(bound: dict, records: list[dict], lex: Lexicon) -> list[str]:
    """
    Calibration check against the workbook's Review sheet.

    Two things had to be corrected to make this measure anything. First, it must
    be restricted to AMBIGUOUS tokens — Tier 1 is unambiguous by construction
    and so is almost never flagged, which makes every other tier look alarming.
    Second, it has to be read per TYPE against a base rate: the Review sheet's
    3,349 forms cover 87% of ambiguous tokens by mass, so a handful of very
    frequent words swamp the token-level view and it shows nothing.
    """
    per_tok = collections.Counter()
    flag_tok = collections.Counter()
    modal: dict[str, collections.Counter] = collections.defaultdict(collections.Counter)
    for rec in records:
        for tok in bound[rec["id"]]["tokens"]:
            if not tok["matchId"]:
                continue
            e = lex.entry[tok["matchId"]]
            if len(lex.candidates(e["search_key"])) < 2:
                continue
            per_tok[tok["tier"]] += 1
            if e["unvocalized"] in lex.review:
                flag_tok[tok["tier"]] += 1
            modal[e["unvocalized"]][tok["tier"]] += 1

    forms = collections.Counter()
    flagged = collections.Counter()
    for form, counts in modal.items():
        tier = counts.most_common(1)[0][0]
        forms[tier] += 1
        if form in lex.review:
            flagged[tier] += 1
    base = sum(flagged.values()) / max(sum(forms.values()), 1)

    L = ["", "## Cross-check against the workbook's Review sheet", "",
         "The Review sheet flags 3,349 forms whose vocalisation the WORKBOOK could not",
         "settle from context. They should be scarce where we are confident and dense",
         "where we are guessing. Measured per form, against the base rate:", "",
         f"{'resolved mostly at':<32}{'forms':>9}{'flagged':>10}{'rate':>8}{'vs base':>10}"]
    for t in (2, 3, 4):
        n, f = forms[t], flagged[t]
        if not n:
            continue
        L.append(f"  {TIER_NAMES[t]:<30}{n:>9,}{f:>10,}{100*f/n:>7.1f}%"
                 f"{100*f/n - 100*base:>+9.1f}")
    L.append(f"  {'base rate (all ambiguous forms)':<30}{sum(forms.values()):>9,}"
             f"{sum(flagged.values()):>10,}{100*base:>7.1f}%{0.0:>+9.1f}")
    t4 = 100 * flagged[4] / max(forms[4], 1)
    L.append("")
    L.append(f"  Flagged forms are enriched {t4 - 100*base:+.1f} points in the "
             f"most-frequent fallback tier and sit at base in the aligned tier, which is "
             f"the clustering the gate asks for.")
    L.append("")
    L.append("  Token-weighted, for completeness — dominated by a few very frequent forms")
    L.append("  and correspondingly uninformative:")
    for t in (2, 3, 4):
        n, f = per_tok[t], flag_tok[t]
        if n:
            L.append(f"    {TIER_NAMES[t]:<28}{n:>12,}{f:>12,}{100*f/n:>7.1f}%")
    return L


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sample", type=int, default=0, help="emit N stratified tokens for audit")
    ap.add_argument("--seed", type=int, default=20260727)
    ap.add_argument("--corpus", default="tajrid")
    args = ap.parse_args()
    out = OUT / args.corpus
    out.mkdir(parents=True, exist_ok=True)

    cfg = load_config(args.corpus)
    records = json.load((out / "records.json").open(encoding="utf-8"))["records"]

    # Both inputs come from the corpus config. Until Phase 1 these were the
    # literals "Tajrid_frequency_tables.xlsx" and "sahih_bukhari_vocalised.csv",
    # with --corpus scoping only the OUTPUT directory — so `bind.py --corpus X`
    # bound X against al-Tajrid's lexicon and Sahih al-Bukhari and reported a
    # merely-failing gate rather than a wrong book.
    try:
        # Neither input is required on its own; what IS required is that the
        # corpus can reach at least one tier that binds anything. A corpus with
        # neither a workbook nor a witness has no evidence and is refused.
        workbook = source_path(cfg, "lexicon", required=False)
        witness_file = source_path(cfg, "vocalisation_reference", required=False)
        if workbook is None and witness_file is None:
            # A third kind of evidence: the source may be vowelled itself.
            # Measured, not declared — a corpus cannot be trusted to know
            # whether its own file carries harakat, and this guard was written
            # before any source did. Shah Wali Allah's Forty is 99.6% vowelled
            # and needs neither a workbook nor a witness; refusing it here
            # would have made Tier 0 unreachable by construction.
            vowelled = sum(
                1 for rec in records[:400]
                for tok in re.findall(r"[\u0621-\u0652\u0670]+", rec["textRaw"])
                if classify(tok) != NONE
            )
            if not vowelled:
                raise ConfigError(
                    f"corpus {args.corpus!r} declares neither `sources.lexicon` "
                    f"nor `sources.vocalisation_reference`, and its source "
                    f"carries no harakat. There is nothing to bind against; "
                    f"segmentation is as far as this corpus can go."
                )
            print(f"NOTE: no workbook and no witness, but the source is "
                  f"vowelled — binding on Tier 0.\n")
    except ConfigError as e:
        print(f"\n{e}\n", file=sys.stderr)
        return 1
    # The ONLY place the pipeline knows a workbook exists. A corpus that
    # declares `sources.lexicon` gets its curated rows through the al-Tajrid
    # adapter; every other corpus passes nothing and derives its inventory
    # from the witness below.
    if workbook is not None:
        import workbook as workbook_adapter
        lex = Lexicon(workbook_adapter.read_surface(workbook),
                      workbook_adapter.read_review(workbook))
    else:
        lex = Lexicon()

    witness_idx = WitnessIndex(witness_file) if witness_file else None
    if witness_idx is not None and workbook is None and not lex.have_analyses:
        print(
            "WARNING: no build/morphology/analyses.json, and this corpus has no\n"
            "         workbook. Every minted entry will carry vowelling with NO\n"
            "         lemma, root or POS of its own -- whatever morphology the\n"
            "         output has will have come from `lexicon_donors` alone, and\n"
            "         root-based navigation will be dead for anything a donor\n"
            "         does not already cover.\n"
            "         Run `python pipeline/analyse.py` first.\n"
        )
    if witness_idx is None:
        print(f"NOTE: corpus {args.corpus!r} declares no vocalisation reference; "
              f"Tier 2 will be skipped.\n")

    # A corpus with no workbook takes its inventory from the witness's
    # vocabulary. A corpus WITH one keeps the workbook's inventory: the
    # workbook is a curated set of readings for this text, and flooding it with
    # every vowelling the parent edition happens to use elsewhere would turn
    # settled Tier 1 bindings into Tier 3/4 guesses for no gain.
    if witness_idx is not None and not lex.curated:
        seeded = lex.seed_from_witness(witness_idx)
        print(f"seeded {seeded:,} readings from the witness vocabulary "
              f"(no workbook; this is the candidate inventory)\n")

    bound, stats = bind_corpus(
        records, lex, witness_idx, strip=inline_strip_patterns(cfg)
    )
    if witness_idx is None:
        stats["retrieval"]["skipped"] = True

    # Gloss enrichment from sibling corpora. Runs AFTER binding, so it can only
    # fill in entries this corpus arrived at on its own evidence.
    enriched: dict[str, dict] = {}
    gloss_path = OUT / "glossary" / "glossary.json"
    if cfg.get("use_glossary", True) and gloss_path.exists():
        enriched["glossary"] = lex.enrich_from_glossary(gloss_path)
    for donor_id in (cfg.get("lexicon_donors") or []):
        try:
            donor_cfg = load_config(donor_id)
            donor_path = source_path(donor_cfg, "lexicon", required=True)
            import workbook as workbook_adapter
        except ConfigError as e:
            print(f"NOTE: donor {donor_id!r} unavailable: {e}\n")
            continue
        enriched[donor_id] = lex.enrich_from(
            workbook_adapter.read_lexicography(donor_path), donor_id)
    stats["enrichment"] = enriched

    # Token-weighted morphology coverage, measured after enrichment. Entry
    # counts flatter the result: the head of the distribution is where the
    # donors overlap, so a per-ENTRY figure and a per-TOKEN figure differ by a
    # lot and only the latter describes what a reader meets.
    layer_of = {r["id"]: r["layer"] for r in records}
    morph = collections.Counter()
    for rid, rec in bound.items():
        if layer_of.get(rid) != "matn":
            continue
        for t in rec["tokens"]:
            mid = t["matchId"]
            if not mid:
                continue
            morph["bound"] += 1
            e = lex.entry.get(mid, {})
            for field in ("lemma", "root", "pos"):
                if e.get(field):
                    morph[field] += 1
    stats["morphology"] = {**morph, "have_analyses": lex.have_analyses}

    res = resources_for(cfg, source_has_marks=bool(
        (stats.get("sourceVocalisation") or {}).get(FULL)
        or (stats.get("sourceVocalisation") or {}).get(PARTIAL)))
    lines = report(stats, cfg.get("gates"), res)
    # The hold-out measures Tiers 3 and 4 by hiding the Tier 2 witness and
    # re-deriving the answer. With no witness there is nothing to hide and
    # nothing to measure — the corpus reached its readings another way.
    if stats["tally"].get(2):
        lines += holdout_eval(bound, lex, records)
    lines += ambiguous_review_crosscheck(bound, records, lex)
    print("\n".join(lines))

    OUT.mkdir(parents=True, exist_ok=True)
    # Readings minted from the witness are not in the workbook, so the packager
    # has no other way to learn about them. A sibling file, because
    # bindings.json is a flat map of record id to tokens and must stay one.
    if not lex.curated:
        doc = derive_lexicon(bound, records, lex)
        (out / "lexicon.json").write_text(
            json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        print(f"derived lexicon         {len(doc['surface']):,} readings "
              f"(no workbook; counts measured over this corpus)")

    (out / "minted.json").write_text(
        json.dumps(
            {
                mid: {
                    "match_id": mid,
                    "search_key": lex.entry[mid]["search_key"],
                    "vocalized": lex.entry[mid]["vocalized"],
                    "unvocalized": lex.entry[mid]["unvocalized"],
                    "pos": lex.entry[mid]["pos"],
                    "lemma": lex.entry[mid]["lemma"],
                    "root": lex.entry[mid]["root"],
                    "fromWitness": True,
                    # Enrichment from a sibling corpus. Carried explicitly so
                    # the interface can say WHERE a gloss came from: it belongs
                    # to the word, but it was written for another book.
                    "gloss_msa": lex.entry[mid].get("gloss_msa"),
                    "glossFrom": lex.entry[mid].get("glossFrom"),
                }
                for mid in sorted(lex.minted)
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    print(f"minted from the witness       {len(lex.minted):>7,} readings")

    (out / "bindings.json").write_text(
        json.dumps(bound, ensure_ascii=False), encoding="utf-8"
    )
    print(f"\nwrote {(out / 'bindings.json').relative_to(ROOT.parent)}")

    if args.sample:
        rng = random.Random(args.seed)
        pool = collections.defaultdict(list)
        for rec in records:
            toks = bound[rec["id"]]["tokens"]
            for tok in toks:
                pool[tok["tier"]].append((rec, toks, tok))
        per = max(1, args.sample // 5)
        picks = []
        for t in sorted(TIER_BY_N):
            picks += rng.sample(pool[t], min(per, len(pool[t])))
        L = ["# Phase 3 — stratified audit sample", "",
             f"{len(picks)} tokens, seed {args.seed}. Context shows five words either side; "
             "the bound token is in **bold**.", ""]
        for rec, toks, tok in sorted(picks, key=lambda p: p[2]["tier"]):
            lo, hi = max(0, tok["i"] - 5), min(len(toks), tok["i"] + 6)
            ctx = " ".join(
                (f'**{t["raw"]}**' if t["i"] == tok["i"] else t["raw"]) for t in toks[lo:hi]
            )
            e = lex.entry[tok["matchId"]] if tok["matchId"] else None
            L += [f"### Tier {tok['tier']} — `{rec['id']}`"
                  f"{f' (hadith {rec[chr(110)+chr(117)+chr(109)+chr(98)+chr(101)+chr(114)]})' if rec['number'] else ''}",
                  "", f"Context: {ctx}", "",
                  f"- raw `{tok['raw']}` -> bound **{tok['surface']}**"
                  f" (`{tok['matchId']}`)" if e else f"- raw `{tok['raw']}` -> UNBOUND", ""]
            if e:
                cands = lex.candidates(e["search_key"])
                L += [f"- pos `{e['pos']}`, freq {e['freq']:,}",
                      f"- {len(cands)} candidate(s) on key `{e['search_key']}`: "
                      + ", ".join(f"{lex.entry[c]['vocalized']} ({lex.entry[c]['freq']})"
                                  for c in cands[:6]), ""]
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "phase3_sample.md").write_text("\n".join(L), encoding="utf-8")
        print(f"wrote {(REPORTS/'phase3_sample.md').relative_to(ROOT.parent)}")

    REPORTS.mkdir(parents=True, exist_ok=True)
    (REPORTS / "phase3.md").write_text(
        "# Phase 3 — token binding report\n\n```\n" + "\n".join(lines) + "\n```\n",
        encoding="utf-8",
    )
    # The exit code must agree with the gate line the report printed. It used
    # to recompute its own: a hardcoded `>= 90`, over Tiers 1 and 2 only.
    #
    # That made the process exit 1 on a corpus whose report said PASS — the
    # Muwatta' at 73.0% against its declared 68.0% — and it ignored Tier 0
    # entirely, so a source-vowelled corpus would have been failed for
    # readings that needed no inference at all. One threshold, one set of
    # witnessed tiers, read from the same places `report` reads them.
    matn = stats["tally_matn"]
    total = sum(matn.values()) or 1
    witnessed = 100 * sum(matn[t.n] for t in TIERS if t.witnessed) / total
    threshold = (cfg.get("gates") or {}).get("min_witnessed_matn")
    if threshold is None:
        return 0
    return 0 if witnessed >= threshold else 1


if __name__ == "__main__":
    sys.exit(main())
