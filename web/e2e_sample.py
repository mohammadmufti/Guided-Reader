"""
Generate /tmp/phase7_sample.json for e2e_phase7.py — deterministically, from
the payload itself.

The original sample was produced by a throwaway script and never committed,
which violated the working agreement (SPEC.md §8: a number produced by a
throwaway script is an assertion, not a measurement) and meant the phase 7
gate could not run anywhere but the machine that made it. The first CI run of
the gates failed on exactly that. This script is the throwaway, kept.

No randomness: tokens are taken in reading order (sorted record filenames,
token index), first-N per criterion, so the same payload bytes always yield
the same sample. Change the payload and the sample follows it — which is the
point: the gate tests the payload that is actually shipping.

Usage:
    python e2e_sample.py                       # payload at web/public/data
    python e2e_sample.py --data /tmp/dist/data # CI: the built artifact
"""

from __future__ import annotations

import argparse
import glob
import json
import sys
from pathlib import Path

# How many of each to take. div:* values also satisfy the gate's requirement
# that at least six DISTINCT divergence categories are exercised.
PER_DIVERGENCE = 2
PER_CRITERION = {
    "pos_disagree": 2,
    "root_absent": 6,  # the gate walks these for one still root-less anywhere
    "no_gloss": 2,
    "unbound": 1,
}


def load_surface(data: Path) -> dict:
    """
    Lexical entries, wherever the payload keeps them.

    They moved twice: under `data/corpora/{id}/lex/` when the payload was
    partitioned per corpus, and then to `data/lexicon/` once `share.py`
    deduplicated them across corpora. Both older layouts are still read so this
    works against an artifact built from any of them.
    """
    roots = [data / "lexicon"]                  # shared, current
    if (data / "corpora").exists():             # per-corpus, before share.py
        roots += sorted((data / "corpora").glob("*/lex"))
    roots.append(data / "lex")                  # single-corpus, historical
    surface: dict = {}
    for root in roots:
        for f in sorted(glob.glob(str(root / "surface-*.json"))):
            surface.update(json.loads(Path(f).read_text(encoding="utf-8")))
    return surface


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default=str(Path(__file__).parent / "public" / "data"))
    ap.add_argument("--out", default="/tmp/phase7_sample.json")
    args = ap.parse_args()
    data = Path(args.data)

    surface = load_surface(data)
    if not surface:
        print(f"no surface shards under {data} — is the payload built?", file=sys.stderr)
        return 1

    taken: dict[str, list[dict]] = {}

    def want(criterion: str) -> bool:
        limit = PER_DIVERGENCE if criterion.startswith("div:") else PER_CRITERION.get(criterion, 0)
        return len(taken.get(criterion, [])) < limit

    def take(criterion: str, number: int, i: int) -> None:
        taken.setdefault(criterion, []).append(
            {"criterion": criterion, "number": number, "i": i}
        )

    # Reading order: sorted filenames are stable and match record order closely
    # enough for determinism, which is all that matters here.
    # Records moved under `data/corpora/{id}/` when the payload was
    # partitioned. The sample is al-Tajrid's, because the phase-7 gate asserts
    # against al-Tajrid's own divergence categories; fall back to the flat
    # layout so this still runs against an older artifact.
    record_dir = data / "corpora" / "tajrid" / "hadith"
    if not record_dir.exists():
        record_dir = data / "hadith"
    for f in sorted(glob.glob(str(record_dir / "matn-*.json"))):
        rec = json.loads(Path(f).read_text(encoding="utf-8"))
        number = rec.get("number")
        if not number:
            continue
        for tok in rec["tokens"]:
            i = tok["i"]
            if not tok.get("clickable") or not tok.get("matchId"):
                if want("unbound"):
                    take("unbound", number, i)
                continue
            entry = surface.get(tok["matchId"])
            if not entry:
                continue
            div = entry.get("divergence")
            if div and want(f"div:{div}"):
                take(f"div:{div}", number, i)
            if entry.get("pos_agreement") == "disagree" and want("pos_disagree"):
                take("pos_disagree", number, i)
            if not entry.get("root") and want("root_absent"):
                take("root_absent", number, i)
            if not entry.get("gloss") and want("no_gloss"):
                take("no_gloss", number, i)

    sample = [c for cases in taken.values() for c in cases]

    # The gate hard-requires these; fail HERE, with a clear message, rather
    # than letting phase 7 crash on a missing case.
    required = {"div:curated", "div:not_applicable", "pos_disagree"}
    missing = sorted(required - set(taken))
    if missing:
        print(f"payload yielded no case for: {missing}", file=sys.stderr)
        return 1
    distinct_div = sum(1 for k in taken if k.startswith("div:"))
    if distinct_div < 6:
        print(f"only {distinct_div} divergence categories found; gate needs 6", file=sys.stderr)
        return 1

    Path(args.out).write_text(
        json.dumps(sample, ensure_ascii=False, indent=1), encoding="utf-8"
    )
    print(f"{len(sample)} cases across {len(taken)} criteria -> {args.out}")
    for k in sorted(taken):
        print(f"  {k}: {len(taken[k])}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
