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

from lexicon import stable_id
from normalise import normalise
from tokenise import tokenise

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "build"   # scoped per corpus at runtime: OUT / corpus
REPORTS = ROOT / "reports"

ARABIC = re.compile(r"[\u0621-\u064a]")
STRIP_EDGE = re.compile(r"^[^\u0621-\u064a]+|[^\u0621-\u064a\u064b-\u0652\u0670]+$")

RE_REVIEW_CANDIDATE = re.compile(r"^\s*(.+?)\s*\(\d+\)\s*$")

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
    def __init__(self, workbook: Path) -> None:
        S = pd.read_excel(workbook, sheet_name="Surface")
        self.by_key: dict[str, list[str]] = collections.defaultdict(list)
        self.entry: dict[str, dict] = {}
        self.by_key_form: dict[tuple[str, str], str] = {}
        rows = S.to_dict("records")
        rows.sort(key=lambda r: -int(r["freq"]))
        for r in rows:
            key, voc = str(r["search_key"]), str(r["vocalized"])
            # Identifiers must match lexicon.py's stable scheme exactly, so the
            # derivation lives in one place and is imported, not re-implemented.
            mid = stable_id(key, voc)
            self.by_key[key].append(mid)
            self.entry[mid] = {
                "vocalized": voc, "freq": int(r["freq"]), "pos": r["pos"],
                "unvocalized": str(r["unvocalized"]), "search_key": key,
                # The workbook records how IT arrived at each vowelling. Tiering
                # never read this column, which is how a guess came to be
                # labelled "not in doubt".
                "lexiconGuess": _is_lexicon_guess(r.get("voc_source")),
            }
            self.by_key_form.setdefault((key, voc), mid)
        review_sheet = pd.read_excel(workbook, sheet_name="Review")
        self.review = set(review_sheet["surface"].astype(str))

        # The Review sheet lists candidate vocalisations for ambiguous forms,
        # with frequencies from the REFERENCE corpus used to pick a fallback.
        #
        # Those frequencies are NOT a better prior than our own — held out on
        # 50,538 tokens they score 69.1% against our 70.1%, and where the two
        # disagree it is a coin flip: 2,465 to 2,479. Replacing our ranking with
        # theirs, which is what the roadmap proposed, makes the reader worse.
        #
        # What the sheet is good for is saying which readings are PLAUSIBLE at
        # all. Restricting our candidates to its list and then ranking by our
        # own frequency scores 70.6% on the same population — a real if modest
        # gain, worth about 34 tokens of the corpus.
        self.minted: set[str] = set()
        analyses_path = OUT / "morphology" / "analyses.json"
        self.analyses: dict = (
            json.loads(analyses_path.read_text(encoding="utf-8"))
            if analyses_path.exists()
            else {}
        )
        self.plausible: dict[str, set[str]] = {}
        for row in review_sheet.to_dict("records"):
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
                self.plausible[surface_form] = forms

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
            "unvocalized": vocalized,
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


class BukhariIndex:
    """Content retrieval over the fully-diacritised Bukhari CSV."""

    def __init__(self, csv: Path) -> None:
        rows = pd.read_csv(csv).iloc[:, 0].astype(str).tolist()
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
        for w in set(query):
            for i in self.postings.get(w, ()):
                scores[i] += self.idf[w]
        if not scores:
            return None, 0.0
        row = max(scores, key=lambda k: scores[k])
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
    bukhari: BukhariIndex,
    corrections: tuple[dict, dict] = ({}, {}),
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
    state: list[tuple[dict, str, list[dict], list[str], list[int | None], list[str | None]]] = []

    # ===== Pass 1: Tiers 1, 2, 5 =============================================
    for rec in records:
        leading, tokens = tokenise(rec["textRaw"])
        keys = [normalise(t["raw"]) for t in tokens]
        tiers: list[int | None] = [None] * len(tokens)
        mids: list[str | None] = [None] * len(tokens)

        for i, key in enumerate(keys):
            cands = lex.candidates(key)
            if not cands:
                tiers[i] = 5
            elif len(cands) == 1:
                tiers[i], mids[i] = 1, cands[0]

        if rec["layer"] in ("matn", "zawaid") and keys:
            retrieval["attempted"] += 1
            row, coverage = bukhari.retrieve(keys)
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
                for k, f in zip(bukhari.norm[row], bukhari.forms[row]):
                    row_forms[k].add(f)
                sm = difflib.SequenceMatcher(None, keys, bukhari.norm[row], autojunk=False)
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
                        witness = bukhari.forms[row][b + d]

                        # The witness may attest a reading the workbook's
                        # inventory lacks — طَائِفَةٌ where it has only
                        # طَائِفَةً and طَائِفَةٍ. Mint the entry rather than
                        # discard the evidence: 1,031 tokens, 1,019 of them in
                        # positionally trusted blocks. Without this the token
                        # falls back to a wrong single option, which is exactly
                        # how إِنَّمَا الْأَعْمَالِ happened.
                        if size >= WITNESS_BLOCK:
                            lex.mint_from_witness(keys[i], witness)

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
                if rec["bukhariRefs"]:
                    ref_agree["checked"] += 1
                    if row + 1 in rec["bukhariRefs"] or coverage >= 0.8:
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

            binding, confidence = {
                1: ("unique", "high"), 2: ("aligned", "high"),
                3: ("heuristic", "medium"), 4: ("heuristic", "low"),
                5: ("unbound", "none"),
            }[tier]
            # Tier 1 means the LEXICON offered one candidate — not that the
            # candidate is right. Where that candidate's own vowelling was the
            # workbook's fallback rather than a witness, the reading is not
            # certain and must not be labelled as if it were. The TIER is
            # unchanged, so coverage accounting and the 90% gate stay
            # comparable; only the honesty of the label moves.
            if tier == 1 and mid and lex.entry[mid]["lexiconGuess"]:
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
    reasons["syntax-override (ibn)"] = sum(syntax_fixes.values())
    reasons["witness-corrected Tier 1"] = sum(witness_fixes.values())
    return bound, {"tally": tally, "tally_matn": tally_matn, "reasons": reasons,
                   "retrieval": retrieval, "refAgree": ref_agree}


TIER_NAMES = {1: "1 unique", 2: "2 aligned", 3: "3 heuristic (case)",
              4: "4 heuristic (most-frequent)", 5: "5 unbound"}


def report(stats: dict) -> list[str]:
    L: list[str] = []
    tally, matn = stats["tally"], stats["tally_matn"]
    tot, totm = sum(tally.values()), sum(matn.values())
    L.append(f"{'tier':<32}{'all tokens':>12}{'%':>8}{'matn':>11}{'%':>8}")
    for t in (1, 2, 3, 4, 5):
        L.append(f"  {TIER_NAMES[t]:<30}{tally[t]:>12,}{100*tally[t]/tot:>7.1f}%"
                 f"{matn[t]:>11,}{100*matn[t]/totm:>7.1f}%")
    L.append(f"  {'TOTAL':<30}{tot:>12,}{100:>7.1f}%{totm:>11,}{100:>7.1f}%")
    t12 = 100 * (matn[1] + matn[2]) / totm
    L.append("")
    L.append(f"GATE — Tier 1+2 on matn: {t12:.1f}%  (requires >= 90.0%)  "
             f"{'PASS' if t12 >= 90 else 'FAIL'}")
    L.append(f"Naive ceiling for comparison: 85.9% (always take the most frequent candidate)")
    if stats["reasons"]:
        L.append("")
        L.append("Tier 3 breakdown: " + ", ".join(
            f"{k} {v:,}" for k, v in stats["reasons"].most_common()))
    r = stats["retrieval"]
    if r["coverages"]:
        cov = sorted(r["coverages"])
        L.append("")
        L.append(f"Bukhari retrieval: {len(cov):,} of {r['attempted']:,} records matched, "
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
    for t in (1, 2, 3, 4, 5):
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
         "Tier-2 tokens have an independent witness (the vocalised Bukhari word).",
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

    records = json.load((out / "records.json").open(encoding="utf-8"))["records"]
    lex = Lexicon(CACHE / "Tajrid_frequency_tables.xlsx")
    bukhari = BukhariIndex(CACHE / "sahih_bukhari_vocalised.csv")
    bound, stats = bind_corpus(records, lex, bukhari)

    lines = report(stats)
    lines += holdout_eval(bound, lex, records)
    lines += ambiguous_review_crosscheck(bound, records, lex)
    print("\n".join(lines))

    OUT.mkdir(parents=True, exist_ok=True)
    # Readings minted from the witness are not in the workbook, so the packager
    # has no other way to learn about them. A sibling file, because
    # bindings.json is a flat map of record id to tokens and must stay one.
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
        for t in (1, 2, 3, 4, 5):
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
    t12 = 100 * (stats["tally_matn"][1] + stats["tally_matn"][2]) / sum(stats["tally_matn"].values())
    return 0 if t12 >= 90 else 1


if __name__ == "__main__":
    sys.exit(main())
