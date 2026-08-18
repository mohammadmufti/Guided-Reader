#!/usr/bin/env python3
"""
Run the morphological analysers directly and cache the result.

    python pipeline/analyse.py            # -> build/morphology/analyses.json

WHY. The supplied workbook's own README says its morphology is
`qalsadi` reconciled against Buckwalter/AraMorph. So it is already this output,
cached, filtered through one corpus, and lossy: 409 forms reach us as
`pos=particle` with a one-letter lemma and no root because a reconciliation step
we cannot inspect discarded the stem. Running the analysers ourselves is not
adding an opinion — it is removing an intermediary.

THE CHAIN, and the two dead ends found on the way to it.

    qalsadi.lemmatize(form)  ->  lemma, pos
    arramooz(verbs U nouns)  ->  root, by lemma

`tashaphyne.get_root()` looked like the obvious route and is not: applied to a
surface form it returns the whole word, and applied to a lemma it invents
geminate roots — بعث becomes عثث, بني becomes بنن, خشي becomes خشش. It is a light
stemmer, not a root extractor, and it agreed with the workbook on only 62.4% of
forms. `arramooz` is a real dictionary with a root column and agrees on 92.3%.

BOTH TABLES MUST BE QUERIED. Verbs and nouns are separate dictionaries: بايع
resolves only in verbs, صلاة and بنيان only in nouns. Querying one halves the
coverage silently.

PRECEDENCE. This provider sits BELOW the workbook. Where the workbook has a root,
it keeps it; where it does not, this fills the gap. The two disagree on 4.1% of
forms and neither is authoritative — `حِسَابُكُمَا` is rooted حشر by the workbook
and حسب here, and here is right — so a disagreement is recorded rather than
silently resolved.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
BUILD = ROOT / "build"
OUT = BUILD / "morphology"

sys.path.insert(0, str(ROOT))
from corpus import ConfigError, load_config, source_path
from vocalisation import split_marks as _split_marks
from normalise import dediac, normalise, root_key  # noqa: E402


import re  # noqa: E402

ARABIC_LETTER = re.compile(r"[\u0621-\u064a]")

MARKS = "\u064B-\u0652\u0670"
_GROUPS = re.compile(rf"([^\s{MARKS}])([{MARKS}]*)")


def letters_marks(s: str) -> list[tuple[str, str]]:
    return _GROUPS.findall(s)


def compatible(form: str, voc_lemma: str) -> bool:
    """
    Does the form's own vocalisation admit this candidate reading?

    The candidate's letter skeleton must appear contiguously inside the
    form's (prefixes like \u0648\u064e/\u0627\u0644\u0652 and suffixes sit outside it), and on the
    shared letters every mark BOTH sides wrote must agree — a mark only one
    side wrote is not evidence either way, since neither source vocalises
    exhaustively. The final shared letter's short vowels are ignored,
    because there the candidate carries a citation case and the form a
    contextual one.

    Shadda is compared strictly ONLY where the form vocalised the letter at
    all. The first draft compared it unconditionally, which quietly broke
    the function's own principle on every bare word: صلى with no marks —
    the taslya formula, whose witness happens not to vowel it — REJECTED
    the reading صَلَّى for its shadda and accepted صَلَى by elimination,
    and the reader was told the Prophet's formula means "roast". A letter
    the form wrote marks on and no shadda is still evidence against a
    shadda'd candidate (بْنِ keeps rejecting the coffee bean بُنٌّ); a
    letter the form left bare is not evidence of anything.

    Module-level because the CAMeL bake-off harness applies the SAME test to
    a different candidate source; one implementation, one behaviour.
    """
    gf, gl = letters_marks(form), letters_marks(voc_lemma)
    if not gf or not gl:
        return True
    skel_f = [g[0] for g in gf]
    skel_l = [g[0] for g in gl]
    n, m = len(skel_f), len(skel_l)
    for off in range(n - m + 1):
        if skel_f[off:off + m] != skel_l:
            continue
        ok = True
        for j in range(m):
            mf = set(gf[off + j][1])
            ml = set(gl[j][1])
            if ("\u0651" in mf) != ("\u0651" in ml) and mf:
                # shadda differs, and the form vocalised this letter
                ok = False
                break
            if j == m - 1:
                continue  # citation vs contextual case ending
            shared = (mf - {"\u0651"}) and (ml - {"\u0651"})
            if shared and (mf - {"\u0651"}) != (ml - {"\u0651"}):
                ok = False
                break
        if ok:
            return True
    return False


WEAK_MAP = {"أ": "ء", "إ": "ء", "آ": "ء", "ؤ": "ء", "ئ": "ء", "ء": "ء",
            "ى": "ي", "ي": "ي", "و": "و"}


def build_camel():
    """
    CAMeL Tools over calima-msa-r13, as a root provider.

    Adopted 2026-07-30 on the bake-off's evidence (reports/camel-bakeoff.md):
    it fills 2,391 root gaps the arramooz chain leaves (against 713 the other
    way), and where the two disagree Lane's Lexicon sides with CAMeL 818:321.
    Licensing and lineage are on the record in bakeoff_camel.py — same GPL
    Aramorph posture as arramooz, attribution in NOTICE.md.

    r13 masks weak radicals as '#'. recover() resolves the mask by aligning
    the root against the analysis's own vocalised lemma (أَتَى + '#ت#' ->
    hamza and yā recovered as ءتي); a medial bare alif stays ambiguous and
    the root is DROPPED rather than shipped masked — a student must never
    meet '#'.
    """
    from camel_tools.morphology.analyzer import Analyzer
    from camel_tools.morphology.database import MorphologyDB
    from camel_tools.utils.dediac import dediac_ar

    az = Analyzer(camel_db())

    def recover(root: str, lex: str | None) -> str | None:
        if "#" not in root:
            return root
        skel = [c for c in dediac_ar(lex or "") if c.strip()]
        # Align the root's KNOWN letters as an ordered subsequence of the
        # lemma's skeleton; each '#' then takes the lemma letter it spans.
        # تَكَوَّن + ك#ن: ك and ن anchor at positions 1 and 3, the mask
        # reads position 2 -> و. A '#' spanning zero or several letters, or
        # reading a bare medial alif (كان: و or ي, undecidable from the
        # lemma), stays unresolved here and falls through to the arramooz
        # resolver; failing that the root is DROPPED, never shipped masked.
        n, m = len(skel), len(root)
        pos = -1
        anchors: list[int | None] = []
        ok = True
        for c in root:
            if c == "#":
                anchors.append(None)
                continue
            try:
                pos = skel.index(c, pos + 1)
            except ValueError:
                ok = False
                break
            anchors.append(pos)
        if not ok:
            return None
        out = []
        for i, c in enumerate(root):
            if c != "#":
                out.append(c)
                continue
            lo = anchors[i - 1] + 1 if i and anchors[i - 1] is not None else 0
            hi = next((a for a in anchors[i + 1:] if a is not None), n)
            span = skel[lo:hi]
            if len(span) != 1:
                return None
            fixed = WEAK_MAP.get(span[0])
            if not fixed:
                return None
            out.append(fixed)
        return "".join(out)

    PRONOUN_ENCLITIC = ("_pron", "_poss", "_dobj")

    def clitic_segments(a: dict, form: str) -> list[dict] | None:
        """
        Where the clitic boundaries fall, as LETTER COUNTS.

        Counts, not letters. The reader is shown the source's own spelling, and
        CAMeL's `diac` is its own — returning its letters here would put another
        edition's word on the screen. Counts let the client colour the word it
        already has.

        Kind only: prefix, stem, enclitic. NOT which prefix. CAMeL labels the
        types — `li_prep` against `la_emph` — but gets them wrong in plain
        cases: on `إِنَّ الْأَمْرَ لَيَسِيرٌ` its own disambiguator calls an
        emphatic lam a preposition. Naming it would be asserting something the
        tool does not reliably know.

        Returns None whenever the segmentation cannot be trusted:
          - `bwtok` also splits INFLECTIONAL endings (`صَلا_+َة`), which belong
            to the word. Only a pronoun enclitic is treated as one.
          - the number of leading parts must match the number of proclitic
            features, or the split is not the clitic split.
          - the letter counts must sum to the form's own, or the two
            skeletons disagree and no alignment exists.
        About 92% of forms segment; the rest are shown whole, which is right.
        """
        tok = a.get("bwtok") or ""
        if not tok or tok in ("NOAN", "NTWS"):
            return None
        n_letters = lambda t: len(_split_marks(t)[0])
        head, _, tail_all = tok.rpartition("+_")
        pre = [p for p in head.split("+_") if p] if head else []
        rest = tail_all if head else tok
        pieces = rest.split("_+")
        stem, trailing = pieces[0], [p for p in pieces[1:] if p]

        n_prc = sum(1 for k in ("prc0", "prc1", "prc2", "prc3")
                    if a.get(k) not in (None, "0", "na"))
        if len(pre) != n_prc:
            return None

        keep = bool(trailing) and any(
            m in str(a.get("enc0") or "") for m in PRONOUN_ENCLITIC)
        if keep:
            stem += "".join(trailing[:-1])
            trailing = trailing[-1:]
        else:
            stem += "".join(trailing)
            trailing = []

        out = [{"kind": "prefix", "letters": n_letters(p)} for p in pre if n_letters(p)]
        out.append({"kind": "stem", "letters": n_letters(stem)})
        out += [{"kind": "enclitic", "letters": n_letters(t)} for t in trailing if n_letters(t)]
        if sum(x["letters"] for x in out) != n_letters(form):
            return None
        return out if len(out) > 1 else None

    def camel(form: str, resolve=None, lexOut: list | None = None,
              segOut: list | None = None) -> list[str]:
        """
        Distinct recovered roots. The diacritic test NARROWS when it can and
        steps aside when the DB's marking conventions admit nothing — a
        convention mismatch must not veto a correct root. `resolve(lex,
        masked)` is a second recovery chance for '#' the lemma alignment
        cannot fix (medial alif: كان could be كون or كيع-class) — the
        arramooz rows we already hold usually know the weak letter.
        """
        try:
            analyses = az.analyze(dediac_ar(form))
        except Exception:
            return []
        keep_strict = [a for a in analyses
                       if compatible(form, a.get("diac", ""))]
        # ROOTS may fall back to the full set when nothing is compatible —
        # the DB's marking conventions must not veto a correct root, and
        # root recovery tolerates a wrong sibling in the count. The LEMMA
        # and GLOSS may NOT: they name one reading, and naming the reading
        # the written harakat contradict is how بْنِ — sukun on the ب —
        # was glossed "coffee beans" (بُنٌّ, damma): every analysis failed
        # the diacritic test, the old fallback resurrected all of them,
        # and the best-supported lemma of the wrong set won. No lemma and
        # no gloss is the honest output there; the donor gloss and the
        # bare lemma still say "son".
        keep = keep_strict or analyses
        # Count analyses per recovered root: when several roots survive, the
        # one more analyses support leads. NOT sorted() — this project has
        # already shipped one alphabet-as-tiebreak and will not ship another.
        support: dict[str, int] = {}
        # The VOCALISED lemma, alongside the root. CAMeL states it in `lex`,
        # and it is what Lane indexes an article by: `بَعَث`, not the inflected
        # `بَعَثَكَ` and not the bare `بعث`. The bare lemma cannot use the
        # vocalised matching tier, which is the tier that tells `هِجْرَةٌ` from
        # `هُجْرَةٌ`, so a bare candidate falls through to a tier where six
        # entries look alike.
        lex_support: dict[str, int] = {}
        # `stemgloss`, not `gloss`. The latter decorates the stem with every
        # clitic and case tag — `with;by_+_the+concealment;silence+[def.gen.]`
        # where the word means "concealment". The stem gloss is the word.
        gloss_for: dict[str, str] = {}
        for a in keep_strict:
            _lex = a.get("lex")
            if _lex and _lex not in ("NOAN", "NTWS"):
                lex_support[str(_lex)] = lex_support.get(str(_lex), 0) + 1
                _sg = a.get("stemgloss")
                if _sg and str(_lex) not in gloss_for:
                    gloss_for[str(_lex)] = str(_sg)
        for a in keep:
            r = a.get("root")
            if not r or r in ("NTWS", "NOAN"):
                continue
            r = r.replace(".", "")
            got = recover(r, a.get("lex"))
            if got is None and "#" in r:
                # the surface form often SHOWS the radical the lemma hides:
                # لِتَكُونَ carries the و of كون even though lex كان does not
                got = recover(r, form)
            if got is None and resolve is not None and "#" in r:
                got = resolve(dediac_ar(a.get("lex") or ""), r)
            if got:
                support[got] = support.get(got, 0) + 1
        # `lexOut` carries the best-supported vocalised lemma back to the
        # caller. A list, because the closure has no other channel and the
        # caller must not have to re-run the analyser to get it.
        if segOut is not None and keep:
            seg = clitic_segments(keep[0], form)
            if seg:
                segOut.append(seg)
        if lexOut is not None and lex_support:
            best = max(lex_support, key=lambda k: (lex_support[k], k))
            lexOut.append(best)
            lexOut.append(gloss_for.get(best) or "")
        return sorted(support, key=lambda r: (-support[r], r))

    return camel


def merge_roots(camel_roots: list[str], arr_root: str | None,
                arr_alts: list[str], arr_basis: str | None):
    """
    -> (root, alternatives, basis). Field-level precedence, measured:

      agree        both stacks name the same root — the strongest signal
      camel        they disagree; CAMeL's is shown (Lane sides with it
                   818:321 where they differ — reports/camel-bakeoff.md),
                   the arramooz root is kept visible as an alternative
      camel-only   only CAMeL has one
      arramooz-*   only the arramooz chain has one; its own basis is kept
    """
    def same(a: str, b: str) -> bool:
        return root_key(a) == root_key(b)

    if camel_roots and arr_root:
        hit = next((c for c in camel_roots if same(c, arr_root)), None)
        if hit:
            alts = sorted({r for r in camel_roots + arr_alts if not same(r, arr_root)})
            return arr_root, alts, "agree"
        return (camel_roots[0],
                sorted({*camel_roots[1:], arr_root, *arr_alts}),
                "camel")
    if camel_roots:
        return camel_roots[0], camel_roots[1:], "camel-only"
    if arr_root:
        return arr_root, arr_alts, f"arramooz-{arr_basis}"
    return None, [], None


_CAMEL_DB = None


def camel_db():
    """
    The CAMeL morphology database, opened ONCE for both analysis and generation.

    `builtin_db` with flags `"ag"` serves an Analyzer and a Generator from the
    same tables. Opening it twice — once bare for analysis, once with `"g"` —
    loaded a second copy of the same 339 MB and took the stage to 702 MB peak
    for no gain. The runner has less headroom than this machine, so the second
    copy was a plausible way to fail there and not here.
    """
    global _CAMEL_DB
    if _CAMEL_DB is None:
        from camel_tools.morphology.database import MorphologyDB
        _CAMEL_DB = MorphologyDB.builtin_db("calima-msa-r13", "ag")
    return _CAMEL_DB


def build_verb_forms():
    """
    lemma -> (perfect, imperfect, wazn), for verbs.

    Two citation forms, because one does not fix the scale: samiʿa could be
    yasmaʿu, yasmiʿu or yasmuʿu, and knowing which is the whole point of citing
    a verb as a pair.

    Generation shares the analyser's database — see `camel_db`. It runs once
    here, not per word.

    A wrinkle worth recording: the imperfect generates under mood `u` only.
    `i`, `s` and `j` all return nothing, so asking for the plain indicative is
    the one call that works.
    """
    try:
        from camel_tools.morphology.generator import Generator
        gen = Generator(camel_db())
    except Exception as exc:                       # pragma: no cover
        print(f"  (no generation database: {exc}; verb pairs will be absent)")
        return lambda lex: None

    base = {"pos": "verb", "per": "3", "gen": "m", "num": "s", "vox": "a"}
    cache: dict[str, dict | None] = {}

    def forms(lex: str) -> dict | None:
        if lex in cache:
            return cache[lex]
        out = None
        try:
            perf = gen.generate(lex, {**base, "asp": "p", "mod": "i"})
            impf = gen.generate(lex, {**base, "asp": "i", "mod": "u"})
        except Exception:
            perf = impf = []
        # The LONGEST, not the first alphabetically. The generator offers both
        # the jussive-shaped stem and the full one — `يَقُل` beside `يَقُول` —
        # and the shorter is not the citation form.
        def pick(rows):
            forms = {r["diac"] for r in rows if r.get("diac")}
            return max(sorted(forms), key=len) if forms else None
        p_, i_ = pick(perf), pick(impf)
        # The indicative ending. CAMeL's `diac` gives the stem without the mood
        # vowel — `يَسْمَع`, where a student needs `يَسْمَعُ`, because the whole
        # use of the pair is to show the scale. Added only after a plain
        # consonant: a defective verb ends in its own weak letter (`يَصْلِي`)
        # and takes none.
        if i_ and i_[-1] not in "\u0627\u0648\u064a\u0649" and not (
                "\u064b" <= i_[-1] <= "\u0652"):
            i_ += "\u064f"
        if p_ and i_:
            pat = next((r.get("pattern") for r in impf if r.get("pattern")), None)
            out = {"perfect": p_, "imperfect": i_, "pattern": pat}
        cache[lex] = out
        return out

    return forms


def build_analyser():
    import arramooz.arabicdictionary as ad
    import qalsadi.lemmatizer as ql

    lemmatiser = ql.Lemmatizer()
    # Verbs and nouns are separate tables. Query both, union the ROWS —
    # keeping each row's vocalised lemma, because that is what disambiguates
    # homographs (مُصِرٌّ is صرر; مِصْرٌ is مصر).
    dictionaries = [ad.ArabicDictionary(t) for t in ("verbs", "nouns")]
    rows_cache: dict[str, list[tuple[str, str]]] = {}

    def rows_for(lemma: str) -> list[tuple[str, str]]:
        """(vocalised_lemma, root) pairs, deterministic order."""
        if lemma in rows_cache:
            return rows_cache[lemma]
        found: set[tuple[str, str]] = set()
        for d in dictionaries:
            try:
                for row in d.lookup(lemma) or []:
                    r = dict(row)
                    if r.get("root"):
                        found.add((str(r.get("vocalized") or ""), str(r["root"])))
            except Exception:
                continue
        rows_cache[lemma] = sorted(found)
        return rows_cache[lemma]

    # Lane, as adjudicator: which candidate roots exist as entries at all.
    # (Headword-level matching was tried and adds nothing over existence for
    # this purpose: the fake candidates — خصب for خطاب — are real roots too;
    # what kills them is losing the vocalisation and majority rounds. Lane
    # existence only breaks the residual ties.)
    lane_roots: set[str] = set()
    lane_path = OUT.parent / "lane" / "entries.json"
    if lane_path.exists():
        lane_roots = {root_key(k) for k in json.loads(
            lane_path.read_text(encoding="utf-8"))}

    def choose_root(form: str, lemma: str):
        """
        -> (root, alternatives, basis). The old code took sorted(roots)[0] —
        the ARABIC ALPHABET as tiebreak — which is how خطاب shipped as خصب
        and مصر as صرر. Rounds, each narrowing the last:

          vocalised  rows whose vocalised lemma the form's own marks admit
          majority   the root more dictionary rows vote for
          lane       a candidate that is a real Lane entry beats one that isn't
          unresolved deterministic, and SAID to be arbitrary
        """
        rows = rows_for(lemma)
        if not rows:
            return None, [], None
        all_roots = sorted({r for _, r in rows})
        if len(all_roots) == 1:
            return all_roots[0], [], "unanimous"

        pool = [(v, r) for v, r in rows if compatible(form, v)] or rows
        basis = "vocalised" if len(pool) < len(rows) else None
        tally: dict[str, int] = {}
        for _, r in pool:
            tally[r] = tally.get(r, 0) + 1
        best = max(tally.values())
        leaders = sorted(r for r, c in tally.items() if c == best)
        if len(leaders) == 1:
            winner = leaders[0]
            basis = basis or "majority"
        else:
            in_lane = [r for r in leaders if root_key(r) in lane_roots]
            if len(in_lane) == 1:
                winner, basis = in_lane[0], "lane"
            else:
                winner, basis = leaders[0], "unresolved"
        return winner, [r for r in all_roots if r != winner], basis

    camel = build_camel()

    def resolve_masked(lex: str, masked: str) -> str | None:
        """كان + ك#ن: the arramooz rows for the lemma carry the real weak
        letter (كون). Accept a row's root when it matches the mask —
        same letters where the mask has letters, a weak letter under '#'."""
        for _, r in rows_for(lex):
            if len(r) != len(masked):
                continue
            if all(m == "#" and c in "ويء" or m == c
                   for m, c in zip(masked, r)):
                return r
        return None

    verb_forms = build_verb_forms()

    def analyse(form: str) -> dict | None:
        camel_lex: list[str] = []
        camel_seg: list = []
        camel_roots = camel(form, resolve_masked, camel_lex, camel_seg)
        lemma = pos = None
        arr_root, arr_alts, arr_basis = None, [], None
        try:
            got = lemmatiser.lemmatize(form, return_pos=True)
        except Exception:
            got = None
        # THE VOCALISED FORM HIDES ITS OWN CLASS from qalsadi: هُوَ, أَيْضًا
        # and بِهَؤُلَاءِ all come back pos="all" — unknown — where their
        # bare spellings answer "stopword" at once, and the pipeline
        # downstream nulls "all". Every minted pronoun therefore shipped
        # with NO pos, took the open-vocabulary Lane path, and the
        # exists-only fallback gave هُوَ the bare-letter article ه — which
        # the shared merge then stitched onto al-Tajrid's pos=particle row,
        # a chimera no single corpus built (the CI catch). Retry on the
        # dediacritised form, and take its lemma too, which arrives with
        # the clitics stripped (بِهَؤُلَاءِ -> هؤلاء). FILLS ONLY: a
        # definite pos from the vocalised parse stands, even a wrong one —
        # the bare form would call the verb نَوَى a stopword, and quietly
        # reclassifying every vocalised verb whose rasm sits on the
        # stopword list is a far worse trade than كُلَّمَا keeping the
        # verb reading its harakat genuinely parse as.
        if got and got[0] and str(got[1] if len(got) > 1 else "") in ("all", ""):
            try:
                bare = lemmatiser.lemmatize(dediac(form), return_pos=True)
            except Exception:
                bare = None
            if bare and bare[0] and str(bare[1] if len(bare) > 1 else "") \
                    not in ("all", ""):
                got = bare
        if got and got[0]:
            lemma, pos = str(got[0]), (str(got[1]) if len(got) > 1 else None)
            arr_root, arr_alts, arr_basis = choose_root(form, lemma)
        if not lemma and not camel_roots:
            return None
        root, alternatives, basis = merge_roots(
            camel_roots, arr_root, arr_alts, arr_basis)
        return {
            "lemma": lemma,
            # The vocalised lemma, for looking Lane up by headword. Kept beside
            # the bare one rather than replacing it: the bare lemma is the join
            # key everything else already uses.
            "lemmaVocalised": camel_lex[0] if camel_lex else None,
            # A short modern gloss for the lemma. Lane is deeper and older;
            # this is the line a reader can use at a glance, and it exists for
            # words no workbook covers.
            "glossCamel": (camel_lex[1] or None) if len(camel_lex) > 1 else None,
            # Clitic boundaries, as letter counts. See `clitic_segments`.
            "segments": camel_seg[0] if camel_seg else None,
            # The two citation forms of a verb, and the scale they set.
            "verb": (verb_forms(camel_lex[0])
                     if camel_lex and pos == "verb" else None),
            "pos": pos if pos not in ("all", "") else None,
            "root": root,
            "rootAlternatives": alternatives,
            "rootBasis": basis,
        }

    return analyse


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="tajrid")
    ap.add_argument("--workbook", default=None,
                    help="override; normally resolved from the corpus config")
    ap.add_argument("--limit", type=int, default=0, help="for a quick smoke run")
    args = ap.parse_args()

    import pandas as pd

    cfg = load_config(args.corpus)
    try:
        path = Path(args.workbook) if args.workbook else source_path(cfg, "lexicon")
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1
    if not path.exists():
        print(f"no workbook at {path}", file=sys.stderr)
        return 1

    surface = pd.read_excel(path, sheet_name="Surface")
    forms = [str(v) for v in surface["vocalized"]]

    # ---- and every token of every corpus ---------------------------------
    #
    # This stage used to read the workbook alone. The workbook belongs to
    # al-Tajrid, so a word that occurs in another book and not in al-Tajrid was
    # never shown to an analyser at all. Measured on the Muwatta': 10,208 tokens
    # bound to nothing, and 111 of them had an analysis.
    #
    # A sample of 300 of those unbound forms says what it cost. CAMeL finds a
    # root for 264, and that root already has a Lane entry. The pipeline simply
    # did not ask.
    #
    # Analysing them here means a corpus without a workbook still gets a lemma,
    # a root and a part of speech for its own vocabulary — which is what makes
    # a word clickable and what Lane is looked up by.
    from tokenise import tokenise as _tokenise
    corpora_dir = ROOT / "corpora"
    seen_corpora = 0
    for cfg_path in sorted(corpora_dir.glob("*.yaml")):
        recs = BUILD / cfg_path.stem / "records.json"
        if not recs.exists():
            continue
        seen_corpora += 1
        doc = json.loads(recs.read_text(encoding="utf-8"))
        n_before = len(forms)
        seen_forms = set(forms)
        for rec in doc["records"]:
            _, toks = _tokenise(rec["textRaw"])
            for t in toks:
                if t["raw"] not in seen_forms:
                    seen_forms.add(t["raw"])
                    forms.append(t["raw"])
        print(f"  + {len(forms) - n_before:,} forms from {cfg_path.stem}")

    # REFUSE TO RUN BLIND. This stage exists to analyse the corpora, and a
    # corpus with no records.json contributes nothing. Skipping quietly is what
    # shipped a reader with no roots: CI ran this before segmentation, the loop
    # above found nothing, and the workbook-only analysis looked like a normal
    # result. Segment first.
    if seen_corpora == 0:
        print(
            "\nNO CORPUS RECORDS FOUND under pipeline/build/*/records.json.\n"
            "This stage analyses every corpus's tokens, so running it before\n"
            "segmentation produces a workbook-only analysis and every word the\n"
            "workbook lacks loses its root.\n"
            "Run `python pipeline/segment.py --corpus <id>` first.\n",
            file=sys.stderr,
        )
        return 1

    # Also analyse forms the WITNESS attests that the workbook lacks.
    #
    # The workbook's inventory is bounded by what this corpus happened to
    # produce, so it holds طَائِفَةً and طَائِفَةٍ but not طَائِفَةٌ, and
    # أَصْبَحْتُ but not أَصْبَحْتَ. When the aligner meets the missing reading it
    # has nowhere to bind it and the token falls back to a wrong single option —
    # which is the الْأَعْمَالِ failure exactly. 1,031 tokens are in that position.
    #
    # Restricted to keys the workbook already knows, so this widens the READINGS
    # of known words rather than importing Bukhari's isnad vocabulary wholesale.
    witness = source_path(cfg, "vocalisation_reference", required=False)
    if witness is not None and witness.exists():
        keys = {normalise(f) for f in forms}
        seen = set(forms)
        import csv

        with witness.open(encoding="utf-8", newline="") as fh:
            for row in csv.reader(fh):
                for cell in row[:1]:
                    for tok in cell.split():
                        tok = tok.strip("()[]{}«».,،؛:؟!\"'")
                        if not tok or tok in seen:
                            continue
                        if normalise(tok) in keys:
                            seen.add(tok)
                            forms.append(tok)
        print(f"  workbook forms + witness readings: {len(forms):,}", file=sys.stderr)

    # ---- and every OTHER corpus's witness, unrestricted --------------------
    #
    # The restriction above is right for al-Tajrid: its inventory comes from a
    # workbook, and the witness only widens the readings of words the workbook
    # already knows.
    #
    # It is wrong for every other corpus, because their inventory IS the
    # witness. Each token's displayed surface is a vocalised witness form, and
    # `mint_from_witness` looks the analysis up BY THAT FORM. A form that was
    # never analysed produces an entry with no lemma and no root — so Nawawi
    # showed "no root" for الصَّلَاةَ and عَظِيمٍ, whose bare forms were
    # analysed and whose vocalised ones were not.
    from bind import WitnessIndex
    seen_all = set(forms)
    for cfg_path in sorted((ROOT / "corpora").glob("*.yaml")):
        if cfg_path.stem == args.corpus:
            continue
        try:
            other = load_config(cfg_path.stem)
            wit = source_path(other, "vocalisation_reference", required=False)
        except ConfigError:
            continue
        if wit is None or not wit.exists():
            continue
        n_before = len(forms)
        for row in WitnessIndex._read(wit):
            for tok in str(row).split():
                tok = tok.strip("()[]{}«».,،؛:؟!\"'")
                if tok and tok not in seen_all and ARABIC_LETTER.search(tok):
                    seen_all.add(tok)
                    forms.append(tok)
        print(f"  + {len(forms) - n_before:,} witness readings from {cfg_path.stem}")

    if args.limit:
        forms = forms[: args.limit]

    analyse = build_analyser()
    out: dict[str, dict] = {}
    for n, form in enumerate(forms, 1):
        if form in out:
            continue
        got = analyse(form)
        if got:
            out[form] = got
        if n % 5000 == 0:
            print(f"  {n:,}/{len(forms):,}", file=sys.stderr)

    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / "analyses.json"
    target.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")

    with_root = sum(1 for v in out.values() if v["root"])
    disputed = sum(1 for v in out.values() if v["rootAlternatives"])
    print(f"analysed        {len(out):,} forms")
    print(f"  with a root   {with_root:,}  ({100*with_root/len(out):.1f}%)")
    print(f"  root disputed {disputed:,}  (dictionaries offer more than one)")
    print(f"\nwrote {target.relative_to(ROOT.parent)} ({target.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
