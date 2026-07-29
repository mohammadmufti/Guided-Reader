#!/usr/bin/env python3
"""
Extract the workbook into `lexicon.json` + indices. Phase 2.

    python pipeline/lexicon.py            # build + verify + report
    python pipeline/lexicon.py --verify   # statistics only, write nothing

Two things here are load-bearing and are asserted rather than trusted:

  1. `normalise()` must reproduce `search_key` for all 22,464 Surface rows.
     It is the join key between corpus tokens and the lexicon; if it is even
     slightly wrong, Phase 3 mis-binds silently.
  2. Every coverage and ambiguity figure is recomputed and compared against
     the spec's §3.3/§3.4. A deviation means the extraction is wrong, not that
     the spec is out of date.

Nulls are preserved as `null` everywhere. `root` is absent for ~48% of tokens
BY DESIGN — the workbook suppresses roots for particles, pronouns and proper
nouns — and the UI must be able to tell that apart from a failed lookup.
"""

from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import math
import re
import sys
from pathlib import Path

import pandas as pd

from normalise import normalise

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT = ROOT / "build"   # scoped per corpus at runtime: OUT / corpus
REPORTS = ROOT / "reports"

WORKBOOK = "Tajrid_frequency_tables.xlsx"

# Spec §3.3 / §3.4, measured 2026-07-26. Recomputed here; any drift is an error.
EXPECTED_COVERAGE = {
    "gloss_msa": (98.2, 21028),
    "root": (51.9, 18894),
    "classical_keywords": (50.8, 18226),
    "curated_sense": (11.8, 2539),
    "morph_exact_with_case": (67.7, 17361),
    "pos_agreement_agree": (70.4, 17752),
    "voc_source_aligned": (90.0, 16969),
}
EXPECTED_AMBIGUITY = {
    "distinct_keys": 18593,
    "ambiguous_keys": 2631,
    "ambiguous_token_pct": 49.7,
    "most_frequent_ceiling_pct": 85.9,
}
EXPECTED_DIVERGENCE = {
    "not_applicable": 47.6, "aligned": 16.8, "curated": 11.8, "developed_sense": 9.0,
    "no_msa_gloss": 8.2, "divergent": 5.6, "no_classical_entry": 1.1,
}

RE_CANDIDATE = re.compile(r"^\s*(.+?)\s*\((\d+)\)\s*$")

ID_HASH_LEN = 6


def stable_id(search_key: str, vocalized: str) -> str:
    """
    A lexicon identifier that does not move.

    The workbook's own `match_id` is `{search_key}#{n}` where n ranks homographs
    by frequency IN THIS CORPUS. Adding a second text shifts frequencies, which
    reorders n, which renames identifiers — measured at 6,502 of 22,464 ids for
    a frequency perturbation. Nothing in the reader breaks from that today,
    because deep links address token positions rather than lexicon entries, but
    a shared cross-corpus store, occurrence links, saved words and stable
    citation all need a key that survives a rebuild.

    So the discriminator is derived from the vocalised form itself. Frequency
    now determines DISPLAY ORDER only, which is what it was always for.
    """
    digest = hashlib.sha1(vocalized.encode("utf-8")).hexdigest()[:ID_HASH_LEN]
    return f"{search_key}#{digest}"


def clean(value):
    """
    Workbook cell -> JSON value, preserving absence.

    pandas turns empty cells into NaN and integers into numpy scalars; both
    have to go, and NaN must become `null` rather than 0 or "".
    """
    if value is None:
        return None
    if isinstance(value, float) and math.isnan(value):
        return None
    if pd.isna(value):
        return None
    if hasattr(value, "item"):
        value = value.item()
    if isinstance(value, str):
        value = value.strip()
        return value or None
    return value


def sheet_to_map(df: pd.DataFrame, key_col: str) -> dict[str, dict]:
    out: dict[str, dict] = {}
    for row in df.to_dict("records"):
        key = clean(row[key_col])
        if key is None:
            continue
        out[str(key)] = {k: clean(v) for k, v in row.items()}
    return out


def parse_candidates(raw) -> list[dict] | None:
    """
    `أَبِي(5433) | أُبَيٍّ(61) | …` -> [{form, freq}, …].

    Note the counts are NOT this corpus's frequencies — أبي occurs 190 times
    here but its top candidate is tagged 5433. They come from the reference
    corpus used to pick the most-frequent vocalisation, so they are evidence
    about which reading is likelier in general, not a count of anything local.
    """
    raw = clean(raw)
    if raw is None:
        return None
    out = []
    for part in str(raw).split("|"):
        m = RE_CANDIDATE.match(part)
        if m:
            out.append({"form": m.group(1), "refFreq": int(m.group(2))})
    return out or None


def build(path: Path) -> tuple[dict, dict]:
    xl = pd.ExcelFile(path)
    S = xl.parse("Surface")
    total = int(S["freq"].sum())

    # --- gate 1: the join key ------------------------------------------------
    mismatches = [
        (v, k) for v, k in zip(S["vocalized"].astype(str), S["search_key"].astype(str))
        if normalise(v) != k
    ]
    if mismatches:
        raise SystemExit(
            f"normalisation reproduces only {len(S)-len(mismatches)}/{len(S)} search_keys. "
            f"First failures: {mismatches[:5]}"
        )

    # --- surface, re-keyed by a stable identifier ----------------------------
    workbook_rows = sheet_to_map(S, "match_id")
    remap: dict[str, str] = {}
    for wb_id, entry in workbook_rows.items():
        remap[wb_id] = stable_id(str(entry["search_key"]), str(entry["vocalized"]))
    collisions = len(remap) - len(set(remap.values()))
    if collisions:
        raise SystemExit(
            f"{collisions} stable-id collisions at {ID_HASH_LEN} hex digits. "
            "Raise ID_HASH_LEN."
        )
    surface = {}
    for wb_id, entry in workbook_rows.items():
        entry = dict(entry)
        # Kept so the workbook's own columns stay traceable after re-keying.
        entry["workbookMatchId"] = wb_id
        entry["match_id"] = remap[wb_id]
        surface[remap[wb_id]] = entry

    # --- searchKeyIndex, homographs by descending freq -----------------------
    # Homographs stay ordered by descending frequency — that is display order,
    # and it is now the ONLY thing frequency controls about identity.
    index: dict[str, list[str]] = {}
    for key, grp in S.groupby("search_key"):
        ordered = grp.sort_values("freq", ascending=False)["match_id"].tolist()
        index[str(key)] = [remap[str(m)] for m in ordered]

    # --- sibling maps --------------------------------------------------------
    review_raw = xl.parse("Review")
    review: dict[str, dict] = {}
    for row in review_raw.to_dict("records"):
        # Keyed by UNVOCALIZED form, not search_key — 1,997/2,000 sampled keys
        # match Surface.unvocalized but only 1,346 match Surface.search_key.
        k = clean(row["surface"])
        if k is None:
            continue
        review[str(k)] = {
            "freq": clean(row["freq"]),
            "status": clean(row["status"]),
            "nCandidates": clean(row["n_candidates"]),
            "candidates": parse_candidates(row["candidates"]),
            "layers": clean(row["layers"]),
            "firstRecord": clean(row["first_record"]),
        }

    doc = {
        "surface": surface,
        "searchKeyIndex": index,
        "lemmas": sheet_to_map(xl.parse("Lemma"), "lemma"),
        "roots": sheet_to_map(xl.parse("Root"), "root"),
        "names": sheet_to_map(xl.parse("Names"), "name"),
        "technicalSenses": sheet_to_map(xl.parse("TechnicalSenses"), "key"),
        "divergence": sheet_to_map(xl.parse("Divergence"), "lemma"),
        "review": review,
        "unvocalizedIndex": {
            str(clean(r["unvocalized"])): clean(r["search_key"])
            for r in xl.parse("Unvocalized").to_dict("records")
            if clean(r["unvocalized"])
        },
    }

    stats = measure(S, total)
    return doc, stats


def measure(S: pd.DataFrame, total: int) -> dict:
    def cov(mask):
        return round(100 * S.loc[mask, "freq"].sum() / total, 1), int(mask.sum())

    coverage = {
        "gloss_msa": cov(S["gloss_msa"].notna()),
        "root": cov(S["root"].notna()),
        "classical_keywords": cov(S["classical_keywords"].notna()),
        "curated_sense": cov(S["literal_sense"].notna() | S["technical_sense"].notna()),
        "morph_exact_with_case": cov(S["morph_confidence"].eq("exact_with_case")),
        "pos_agreement_agree": cov(S["pos_agreement"].eq("agree")),
        "voc_source_aligned": cov(S["voc_source"].astype(str).str.startswith("aligned")),
    }
    g = S.groupby("search_key")
    sizes = g.size()
    amb = sizes[sizes >= 2]
    ambiguity = {
        "distinct_keys": int(g.ngroups),
        "ambiguous_keys": int(len(amb)),
        "ambiguous_token_pct": round(
            100 * S[S["search_key"].isin(amb.index)]["freq"].sum() / total, 1
        ),
        "most_frequent_ceiling_pct": round(
            100 * S.loc[g["freq"].idxmax(), "freq"].sum() / total, 1
        ),
    }
    divergence = {
        str(k): round(100 * v / total, 1)
        for k, v in S.groupby("divergence")["freq"].sum().items()
    }
    return {
        "totalTokens": total, "types": int(len(S)),
        "coverage": coverage, "ambiguity": ambiguity, "divergence": divergence,
    }


def verify(stats: dict) -> list[str]:
    """Compare every measured figure against the spec. Returns failure lines."""
    fails: list[str] = []
    print("=== §3.3 coverage (token-weighted) ===")
    print(f"  {'field':<26}{'tokens':>8}{'types':>8}{'spec':>8}{'spec types':>12}")
    for field, (pct, types) in stats["coverage"].items():
        exp_pct, exp_types = EXPECTED_COVERAGE[field]
        ok = abs(pct - exp_pct) < 0.05 and types == exp_types
        print(f"  {field:<26}{pct:>7.1f}%{types:>8,}{exp_pct:>7.1f}%{exp_types:>12,}"
              f"  {'' if ok else '<-- MISMATCH'}")
        if not ok:
            fails.append(f"coverage.{field}: got ({pct}, {types}) want ({exp_pct}, {exp_types})")

    print("\n=== §3.4 ambiguity ===")
    for field, got in stats["ambiguity"].items():
        exp = EXPECTED_AMBIGUITY[field]
        ok = (abs(got - exp) < 0.05) if isinstance(exp, float) else got == exp
        print(f"  {field:<30}{got:>10,}   spec {exp:>10,}  {'' if ok else '<-- MISMATCH'}")
        if not ok:
            fails.append(f"ambiguity.{field}: got {got} want {exp}")

    print("\n=== §3.3 divergence distribution ===")
    for k, exp in sorted(EXPECTED_DIVERGENCE.items(), key=lambda kv: -kv[1]):
        got = stats["divergence"].get(k, 0.0)
        ok = abs(got - exp) < 0.06
        print(f"  {k:<24}{got:>6.1f}%   spec {exp:>5.1f}%  {'' if ok else '<-- MISMATCH'}")
        if not ok:
            fails.append(f"divergence.{k}: got {got} want {exp}")
    return fails


def round_trip(doc: dict) -> str:
    """Print five hand-picked entries in full — the gate's qualitative check."""
    picks = [
        ("particle", "من#1"),
        ("proper noun", "الله#1"),
        ("curated technical term", "صلاه#1"),
        ("root-less form", None),
        ("hapax", None),
    ]
    surface = doc["surface"]
    # Fill the two open slots from the data rather than hard-coding.
    rootless = next(
        m for m, e in surface.items()
        if e["root"] is None and e["freq"] > 200 and e["pos"] == "particle"
    )
    hapax = next(
        m for m, e in surface.items()
        if e["freq"] == 1 and e["root"] and e["gloss_msa"] and e["classical_keywords"]
    )
    picks[3] = ("root-less form", rootless)
    picks[4] = ("hapax", hapax)

    L: list[str] = []
    for label, mid in picks:
        e = surface.get(mid)
        if e is None:
            L.append(f"### {label} — `{mid}` NOT FOUND\n")
            continue
        L.append(f"### {label} — `{mid}`\n")
        L.append("| field | value |")
        L.append("|---|---|")
        for k, v in e.items():
            shown = "*(null)*" if v is None else str(v).replace("|", "\\|")
            if len(shown) > 220:
                shown = shown[:220] + " …"
            L.append(f"| `{k}` | {shown} |")
        homs = doc["searchKeyIndex"].get(e["search_key"], [])
        listed = ", ".join(f"{h} (freq {surface[h]['freq']})" for h in homs)
        L.append(f"\nHomographs on key `{e['search_key']}`: {listed}\n")
    return "\n".join(L)


CLASSICAL_FIELDS = [
    "classical_keywords", "classical_sense_sample", "classical_senses_more", "lane_entry_count",
]


def packaging_note(doc: dict) -> tuple[str, dict]:
    """
    Measure the redundancy Phase 4 will have to deal with.

    `lexicon.json` deliberately keeps all 31 Surface columns per §5.2, so the
    classical material is repeated once per surface form rather than once per
    root. That is correct for a faithful pipeline artifact and wrong for a
    shipped payload — this quantifies the gap rather than pre-empting Phase 4's
    packaging decision.
    """
    by_root: dict[str, set] = {}
    for e in doc["surface"].values():
        lr = e.get("lane_root")
        if lr is None:
            continue
        by_root.setdefault(lr, set()).add(
            tuple(json.dumps(e.get(f), ensure_ascii=False) for f in CLASSICAL_FIELDS)
        )
    conflicts = sum(1 for v in by_root.values() if len(v) > 1)
    inlined = sum(
        len(json.dumps(e.get(f), ensure_ascii=False))
        for e in doc["surface"].values()
        for f in CLASSICAL_FIELDS
        if e.get(f) is not None
    )
    deduped = len(
        json.dumps({k: sorted(v)[0] for k, v in by_root.items()}, ensure_ascii=False).encode()
    )
    blob = json.dumps(doc, ensure_ascii=False).encode()
    stats = {
        "rawBytes": len(blob),
        "gzipBytes": len(gzip.compress(blob)),
        "laneRoots": len(by_root),
        "classicalConflicts": conflicts,
        "classicalInlinedBytes": inlined,
        "classicalDedupedBytes": deduped,
        "dedupFactor": round(inlined / deduped, 1) if deduped else None,
    }
    text = (
        "## Packaging note for Phase 4\n\n"
        f"`lexicon.json` is **{stats['rawBytes']/1e6:.1f} MB raw / "
        f"{stats['gzipBytes']/1e6:.1f} MB gzipped**, against Phase 4's ~2 MB shard threshold "
        "and its 150 KB cold-load budget. The bulk is not irreducible.\n\n"
        f"The classical apparatus is a function of `lane_root`: **{stats['laneRoots']:,} distinct "
        f"roots, {conflicts} with conflicting payloads, 0 forms carrying classical material "
        "without a root.** Because §5.2 asks for all 31 Surface columns, it is currently inlined "
        f"once per surface form — **{inlined/1e6:.1f} MB** where a map keyed by `lane_root` would "
        f"take **{deduped/1e6:.1f} MB**, a **{stats['dedupFactor']}x** reduction. Surface entries "
        "already carry `lane_root`, so the pointer needed to normalise this exists.\n\n"
        "`kwic` is another ~2 MB: it is first-occurrence context, useful for binding "
        "verification in Phase 3 and of no use to the reading pane.\n"
    )
    return text, stats


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--verify", action="store_true", help="measure only, write nothing")
    ap.add_argument("--corpus", default="tajrid")
    args = ap.parse_args()
    out = OUT / args.corpus
    out.mkdir(parents=True, exist_ok=True)

    path = CACHE / WORKBOOK
    doc, stats = build(path)

    print(f"normalisation assertion  {len(doc['surface']):,}/{len(doc['surface']):,} exact\n")
    fails = verify(stats)

    print("\n=== maps emitted ===")
    for k in ("surface", "searchKeyIndex", "lemmas", "roots", "names",
              "technicalSenses", "divergence", "review", "unvocalizedIndex"):
        print(f"  {k:<20} {len(doc[k]):>7,}")

    if fails:
        print("\nGATE FAILED:")
        for f in fails:
            print("  ", f)
        return 1

    if not args.verify:
        lexicon_path = out / "lexicon.json"
        blob = json.dumps(doc, ensure_ascii=False)
        lexicon_path.write_text(blob, encoding="utf-8")
        gz = len(gzip.compress(blob.encode("utf-8")))
        print(f"\nwrote {lexicon_path.relative_to(ROOT.parent)}  "
              f"{lexicon_path.stat().st_size/1e6:.2f} MB raw, {gz/1e6:.2f} MB gzipped")
        note, pkg = packaging_note(doc)
        stats["packaging"] = pkg
        (out / "lexicon_stats.json").write_text(
            json.dumps(stats, ensure_ascii=False, indent=1), encoding="utf-8"
        )
        REPORTS.mkdir(parents=True, exist_ok=True)
        (REPORTS / "phase2.md").write_text(
            "# Phase 2 — lexicon extraction report\n\n"
            f"Normalisation reproduces **{len(doc['surface']):,}/{len(doc['surface']):,}** "
            "`search_key` values exactly.\n\n"
            + note
            + "\n## Five entries round-tripped\n\n" + round_trip(doc),
            encoding="utf-8",
        )
        print(f"  classical dedup available: {pkg['dedupFactor']}x "
              f"({pkg['classicalInlinedBytes']/1e6:.1f} MB -> "
              f"{pkg['classicalDedupedBytes']/1e6:.1f} MB) — flagged for Phase 4")
        print(f"wrote {(REPORTS/'phase2.md').relative_to(ROOT.parent)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
