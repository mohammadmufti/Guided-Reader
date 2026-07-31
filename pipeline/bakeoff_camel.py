#!/usr/bin/env python3
"""
Bake-off: CAMeL Tools (calima-msa-r13) against the current qalsadi+arramooz
chain, on this project's own forms.

    python pipeline/bakeoff_camel.py        # -> reports/camel-bakeoff.md
                                            #    build/bakeoff/camel.json
                                            #    build/bakeoff/disagreements.json

This is an EXPERIMENT, not a provider. Nothing here touches the payload or
CI. Per ROADMAP principle 3, CAMeL enters production only as a tier with a
measured error rate — and the measurement that decides is the hand-checked
gold sample (pipeline/gold), because tool-vs-tool agreement cannot crown a
winner when the tools share ancestry:

  LICENSING AND LINEAGE, on the record (see the session of 2026-07-30):
  - camel-tools code is MIT.
  - calima-msa-r13 is Aramorph-1.2.1-derived, GPL, (c) QAMUS/UPenn via LDC —
    the SAME posture as arramooz (GPL, build-time tool, extracted facts in
    the payload, attribution in NOTICE.md), and the SAME 2002 Buckwalter
    lexicon lineage the workbook was reconciled against. A cleaner engine
    over a cousin lexicon; not an independent referee.
  - calima-msa-s31 ships deliberately obfuscated; unmuddling requires the
    LDC SAMA 3.1 distribution as key material. Usable only if that licence
    is purchased. Do not route around the gate.

r13 masks weak radicals as '#' (كان -> ك.#.ن). For SCORING, comparison is
weak-tolerant ('#' matches و/ي/ء/ا at that position). For any future
ADOPTION, recover_radicals() resolves '#' through the arramooz rows we
already hold; its coverage is reported so the residue is a known number,
not a surprise.
"""

from __future__ import annotations

import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from analyse import compatible  # noqa: E402  one implementation, one behaviour
from normalise import root_key  # noqa: E402

BUILD = ROOT / "build"
REPORTS = ROOT / "reports"


def camel_root_str(r: str | None) -> str | None:
    """'خ.ط.ب' -> 'خطب'; keeps '#' placeholders; None for non-roots."""
    if not r or r in ("NTWS", "NOAN") or "." not in r and len(r) > 4:
        return None
    return r.replace(".", "")


def weak_tolerant_equal(a: str | None, b: str | None) -> bool:
    """Root equality where '#' (r13's masked weak radical) matches any of
    و ي ء ا at that position, compared through the project's root_key."""
    if not a or not b:
        return False
    ka, kb = root_key(a.replace("#", "و")), root_key(b)
    if len(ka) != len(kb):
        return False
    for ca, cb, raw in zip(ka, kb, a):
        if raw == "#":
            if cb not in "ويءا":
                return False
        elif ca != cb:
            return False
    return True


def build_camel(forms: list[str]):
    from camel_tools.morphology.analyzer import Analyzer
    from camel_tools.morphology.database import MorphologyDB
    from camel_tools.utils.dediac import dediac_ar

    az = Analyzer(MorphologyDB.builtin_db("calima-msa-r13"))
    out: dict[str, dict] = {}
    for i, form in enumerate(forms):
        if i and i % 5000 == 0:
            print(f"  {i:,}/{len(forms):,}")
        try:
            analyses = az.analyze(dediac_ar(form))
        except Exception:
            analyses = []
        if not analyses:
            out[form] = {"roots": [], "filtered": [], "n": 0}
            continue
        roots_all = sorted({r for a in analyses
                            if (r := camel_root_str(a.get("root")))})
        # the same admission test the arramooz selection uses, applied to
        # each analysis's own full diacritisation
        filt = sorted({r for a in analyses
                       if (r := camel_root_str(a.get("root")))
                       and compatible(form, a.get("diac", ""))})
        out[form] = {"roots": roots_all, "filtered": filt or roots_all,
                     "n": len(analyses),
                     "lex": next((a.get("lex") for a in analyses), None)}
    return out


def recover_radicals(camel: dict, ours: dict) -> tuple[int, int]:
    """Resolve '#' via the arramooz-derived root we already computed for the
    same form, when the two agree weak-tolerantly. Returns (resolved, masked)."""
    masked = resolved = 0
    for form, c in camel.items():
        fixed = []
        for r in c["filtered"]:
            if "#" not in r:
                fixed.append(r)
                continue
            masked += 1
            mine = (ours.get(form) or {}).get("root")
            if mine and weak_tolerant_equal(r, mine):
                fixed.append(mine)
                resolved += 1
            else:
                fixed.append(r)
        c["filtered"] = fixed
    return resolved, masked


def main() -> int:
    analyses_path = BUILD / "morphology" / "analyses.json"
    if not analyses_path.exists():
        print("run pipeline/analyse.py first", file=sys.stderr)
        return 1
    ours = json.loads(analyses_path.read_text(encoding="utf-8"))
    forms = sorted(ours.keys())
    print(f"{len(forms):,} forms")

    camel = build_camel(forms)
    resolved, masked = recover_radicals(camel, ours)

    lane_roots: set[str] = set()
    lane_path = BUILD / "lane" / "entries.json"
    if lane_path.exists():
        lane_roots = {root_key(k) for k in
                      json.loads(lane_path.read_text(encoding="utf-8"))}

    n_covered = n_unique = 0
    agree = disagree = only_ours = only_camel = neither = 0
    lane_ours = lane_camel = lane_both = lane_neither = 0
    disagreements = []
    for form in forms:
        mine = (ours.get(form) or {}).get("root")
        c = camel[form]
        croots = c["filtered"]
        if croots:
            n_covered += 1
            if len(croots) == 1:
                n_unique += 1
        if not mine and not croots:
            neither += 1
            continue
        if mine and not croots:
            only_ours += 1
            continue
        if croots and not mine:
            only_camel += 1
            continue
        if any(weak_tolerant_equal(r, mine) or root_key(r) == root_key(mine)
               for r in croots):
            agree += 1
            continue
        disagree += 1
        o_in = root_key(mine) in lane_roots
        c_in = any(root_key(r.replace("#", "و")) in lane_roots for r in croots)
        lane_both += o_in and c_in
        lane_ours += o_in and not c_in
        lane_camel += c_in and not o_in
        lane_neither += not o_in and not c_in
        disagreements.append({
            "form": form, "ours": mine,
            "oursBasis": (ours.get(form) or {}).get("rootBasis"),
            "camel": croots, "camelLex": c.get("lex"),
            "laneHasOurs": o_in, "laneHasCamels": c_in,
        })

    both = agree + disagree
    out = BUILD / "bakeoff"
    out.mkdir(parents=True, exist_ok=True)
    (out / "camel.json").write_text(
        json.dumps(camel, ensure_ascii=False), encoding="utf-8")
    (out / "disagreements.json").write_text(
        json.dumps(disagreements, ensure_ascii=False, indent=1), encoding="utf-8")

    basis = Counter(d["oursBasis"] for d in disagreements)
    lines = [
        "# CAMeL (calima-msa-r13) vs qalsadi+arramooz — roots",
        "",
        "Agreement is NOT accuracy; the two stacks share Buckwalter-lexicon",
        "ancestry (see bakeoff_camel.py header). The decider is the gold",
        "sample. This report maps where they differ and what Lane says there.",
        "",
        f"| forms analysed | {len(forms):,} |",
        "|---|--:|",
        f"| CAMeL covers | {n_covered:,} ({100*n_covered/len(forms):.1f}%) |",
        f"| CAMeL unique after diacritic filter | {n_unique:,} |",
        f"| masked weak radicals | {masked:,}, resolved via arramooz {resolved:,} |",
        f"| both have a root | {both:,} |",
        f"| **agree** | **{agree:,} ({100*agree/both:.1f}%)** |",
        f"| disagree | {disagree:,} |",
        f"| only ours has a root | {only_ours:,} |",
        f"| only CAMeL has a root | {only_camel:,} |",
        f"| neither | {neither:,} |",
        "",
        "## The disagreements, adjudicated by Lane existence",
        "",
        "| Lane has | count |",
        "|---|--:|",
        f"| only our root | {lane_ours:,} |",
        f"| only CAMeL's | {lane_camel:,} |",
        f"| both (Lane cannot decide) | {lane_both:,} |",
        f"| neither | {lane_neither:,} |",
        "",
        "## Our basis where they disagree",
        "",
        "| basis | count |", "|---|--:|",
        *[f"| {k} | {v:,} |" for k, v in basis.most_common()],
        "",
        "Disagreements: `pipeline/build/bakeoff/disagreements.json` — keyed by",
        "vocalised form so gold verdicts join directly when they exist.",
    ]
    REPORTS.mkdir(exist_ok=True)
    (REPORTS / "camel-bakeoff.md").write_text("\n".join(lines), encoding="utf-8")
    print(f"agree {agree:,}/{both:,} ({100*agree/both:.1f}%)  "
          f"disagree {disagree:,}  -> reports/camel-bakeoff.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
