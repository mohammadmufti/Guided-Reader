#!/usr/bin/env python3
"""
Deduplicate lexical entries across corpora into one shared shard set.

    python pipeline/share.py        # after building every corpus

A lexical entry is corpus-independent by construction: `match_id` is
`stable_id(search_key, vocalized)`, derived from the form and never from
frequency. Two books that use the same word in the same reading therefore
produce the same entry, byte for byte -- measured at 6,784 shared entries
between al-Tajrid and the Muwatta', 52.7% of the Muwatta's inventory and about
3.2 MB shipped twice.

That duplication grows linearly with each book added, and every copy is a
cache miss the reader pays for again after switching.

WHAT MOVES AND WHAT DOES NOT
    data/lexicon/surface-NNN.json     SHARED   what a word is
    data/corpora/{id}/lex/stats-NNN.json  PER CORPUS   what it does HERE

That split already existed in `build.py` -- its comment says the split "is what
lets a lexical entry be identical across corpora" -- but nothing had ever spent
it, because one corpus has nothing to share with. `freq`, `rank`, `pct`,
`doc_freq`, `layers` and `first_record` stay per corpus, for the same reason
`glossary.py` refuses to carry them: a shared store holding one book's
statistics would let that book rank another book's candidates.

RE-SHARDING. Each corpus shards on `fnv1a(search_key) % n` with its own `n`
(32 for al-Tajrid, 8 for the Muwatta'), sized to a byte budget. A shared set
needs ONE routing, so entries are re-sharded on a single global `n` recorded as
`shards.sharedSurface`. Statistics keep their corpus's own `shards.surface`, so
the client resolves the two with different moduli -- which is why both numbers
are published rather than one.

MERGING. Where two corpora hold the same `match_id`, the entries agree on
vowelling, lemma, root and gloss because they came from the same glossary. They
can differ in COMPLETENESS: al-Tajrid's entry may carry a curated field that a
witness-minted entry lacks. The richer one wins, field by field, and a
disagreement on a field both fill is reported rather than silently resolved --
it would mean `match_id` had stopped identifying a reading, which is the
assumption this whole file rests on.
"""

from __future__ import annotations

import argparse
import hashlib
import collections

from build import CLOSED_CLASS_POS
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA = ROOT.parent / "web" / "public" / "data"

# Imported, never reimplemented. The hash decides which shard the CLIENT asks
# for, and the shard count is measured against compressed bytes, not estimated.
# A second copy of either rule here would be a second thing to drift.
sys.path.insert(0, str(ROOT))
from build import fnv1a, shard_count  # noqa: E402


def collect_named(corpora: list[Path], stem: str, previous: Path | None) -> dict:
    """
    Merge a corpus-independent shard set by key, richest entry winning.

    `classical-*` holds Lane's headwords keyed by root and `lane-*` holds the
    dictionary entries themselves. Neither is a fact about a corpus -- Lane's
    Lexicon is the same book whichever text you are reading -- but both were
    written per corpus and populated only from that corpus's own lexicon. The
    result was that Lane appeared in al-Tajrid alone: the Muwatta' and Nawawi
    shipped one empty shard each, so a word whose entry pointed at a Lane
    entry pointed at a file that was not there.
    """
    merged: dict = {}
    if previous is not None and previous.exists():
        for shard in sorted(previous.glob(f"{stem}-*.json")):
            merged.update(json.loads(shard.read_text(encoding="utf-8")))
    for corpus_dir in corpora:
        for shard in sorted((corpus_dir / "lex").glob(f"{stem}-*.json")):
            for k, v in json.loads(shard.read_text(encoding="utf-8")).items():
                if k not in merged or len(json.dumps(v)) > len(json.dumps(merged[k])):
                    merged[k] = v
    return merged


# Fields a corpus may deliberately set to None. For these, None is a decision
# and the merge must preserve it rather than treat it as an absent value.
SUPPRESSIBLE = frozenset({"glossQuick"})


def collect(corpora: list[Path], previous: Path | None = None) -> tuple[dict, dict, list[str]]:
    """
    Merge every corpus's surface shards. Returns (entries, provenance, conflicts).

    `previous` is the EXISTING shared set, folded in first. This step deletes a
    corpus's private shards once they are shared, so a later run that finds a
    corpus already emptied would otherwise drop it entirely -- rebuild one
    corpus, re-run this, and every other book's entries vanish from the payload
    with nothing to report it. Re-reading what is already shared makes the step
    idempotent, which it has to be: it is the last thing in the pipeline and
    the most likely to be run twice.
    """
    entries: dict[str, dict] = {}
    seen_in: dict[str, list[str]] = collections.defaultdict(list)
    conflicts: list[str] = []

    carried: set[str] = set()
    if previous is not None and previous.exists():
        for shard in sorted(previous.glob("surface-*.json")):
            for mid, row in json.loads(shard.read_text(encoding="utf-8")).items():
                entries.setdefault(mid, dict(row))
                carried.add(mid)
                seen_in[mid].append("(already shared)")

    for corpus_dir in corpora:
        for shard in sorted((corpus_dir / "lex").glob("surface-*.json")):
            for mid, row in json.loads(shard.read_text(encoding="utf-8")).items():
                seen_in[mid].append(corpus_dir.name)
                existing = entries.get(mid)
                if existing is None:
                    entries[mid] = dict(row)
                    continue
                if mid in carried:
                    # A freshly built corpus REPLACES what was carried forward.
                    # The carry-forward exists so that a corpus which was not
                    # rebuilt keeps its entries; it must not stop a corpus that
                    # WAS rebuilt from correcting one.
                    #
                    # This blocked a real fix. Lane linkage moved from the wrong
                    # article to the right one, al-Tajrid was rebuilt, and the
                    # shared set kept the old pointer because merging only ever
                    # filled absent fields.
                    entries[mid] = dict(row)
                    carried.discard(mid)
                    continue
                # THE LANE PAIR TRAVELS TOGETHER, and never through the
                # generic gap-fill below. lane_root and laneEntry are one
                # decision made by one corpus's resolution against one set
                # of that corpus's analyses; filling lane_root alone from
                # corpus B into a row whose pos and laneEntry came from
                # corpus A manufactured entries no build produced — هُوَ
                # shipped al-Tajrid's pos=particle stitched to a minted
                # corpus's bare-letter article, which is the exists-only
                # link the build itself forbids (the CI catch).
                if not existing.get("lane_root") and row.get("lane_root"):
                    existing["lane_root"] = row.get("lane_root")
                    existing["laneEntry"] = row.get("laneEntry")
                elif (existing.get("lane_root")
                      and existing.get("lane_root") == row.get("lane_root")
                      and not existing.get("laneEntry")
                      and row.get("laneEntry")):
                    # Same article, and the donor resolved the entry inside
                    # it: a strict refinement.
                    existing["laneEntry"] = row.get("laneEntry")
                for field, val in row.items():
                    if field in ("lane_root", "laneEntry"):
                        continue
                    cur = existing.get(field)
                    # A DELIBERATE NULL IS NOT A GAP. `glossQuick` is set to
                    # None by build.py wherever it duplicates the curated
                    # gloss, and filling it from another corpus undoes that
                    # decision — the shared entry then carries both again and a
                    # reader sees the same meaning printed twice.
                    #
                    # This is why the duplicates survived three fixes: each was
                    # correct per corpus, and the merge put them back. It only
                    # showed once two corpora shared enough vocabulary for one
                    # to overwrite the other, which is why a single-corpus
                    # payload never reproduced it.
                    if field in SUPPRESSIBLE and (cur is None or val is None):
                        existing[field] = None
                        continue
                    if cur in (None, "", [], {}):
                        existing[field] = val
                    elif val not in (None, "", [], {}) and cur != val and field in (
                        "vocalized", "search_key", "unvocalized",
                    ):
                        # An identity field disagreeing means match_id no
                        # longer identifies a reading. Loud, not merged.
                        conflicts.append(
                            f"{mid}: {field} {cur!r} != {val!r} "
                            f"({' vs '.join(seen_in[mid][-2:])})"
                        )
    # The merged view must satisfy the same invariant the build enforces
    # per corpus: a closed-class entry links only where an article contains
    # its own headword. The pair-merge above keeps roots and entries from
    # mixing across corpora; this scrub covers the remaining seam, where
    # the merged POS (one corpus knew the word is a particle) meets merged
    # lane fields (another corpus, analysing the vocalised form, did not —
    # qalsadi answers "all" for هُوَ with its harakat on). An exists-only
    # closed-class link is the لَذَّ bug whichever stage assembles it.
    scrubbed = 0
    for e in entries.values():
        if (e.get("pos") in CLOSED_CLASS_POS and e.get("lane_root")
                and not e.get("laneEntry")):
            e["lane_root"] = None
            scrubbed += 1
    if scrubbed:
        print(f"  scrubbed {scrubbed} exists-only closed-class Lane links "
              f"from the merged view")
    # The same hazard for the second dictionary, and STRICTER, because it has
    # no per-headword entries and so no `laneEntry` clause to qualify the link.
    # Every closed-class Lisān link is an exists-only link by construction, and
    # a corpus whose analyser was less sure can gap-fill one in here even when
    # build.py refused it. 7.6% of al-Tajrid's tokens measure this.
    scrubbed_lisan = 0
    for e in entries.values():
        if e.get("pos") in CLOSED_CLASS_POS and e.get("lisan_root"):
            e["lisan_root"] = None
            scrubbed_lisan += 1
    if scrubbed_lisan:
        print(f"  scrubbed {scrubbed_lisan} closed-class Lisān links "
              f"from the merged view")
    return entries, seen_in, conflicts


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--rebuild", action="store_true",
                    help="ignore the existing shared set; drops entries for "
                         "corpora no longer built")
    args = ap.parse_args()

    corpora_root = DATA / "corpora"
    if not corpora_root.exists():
        print("no built corpora; run build.py first", file=sys.stderr)
        return 1
    corpora = sorted(d for d in corpora_root.iterdir() if (d / "index.json").exists())
    if not corpora:
        print("no built corpora", file=sys.stderr)
        return 1

    before = sum(f.stat().st_size
                 for d in corpora for f in (d / "lex").glob("surface-*.json"))
    entries, seen_in, conflicts = collect(
        corpora, None if args.rebuild else DATA / "lexicon")

    if conflicts:
        print(f"REFUSING TO SHARE — {len(conflicts)} identity conflicts.")
        print("  match_id must identify a reading; these say otherwise:")
        for c in conflicts[:10]:
            print(f"    {c}")
        return 1

    # One global routing for the shared set, sized exactly as build.py sizes a
    # corpus's own: smallest power of two whose worst COMPRESSED shard fits the
    # budget. Statistics keep their corpus's `shards.surface`, so the client
    # resolves the two with different moduli.
    n = shard_count(entries, lambda k: k.rsplit("#", 1)[0])

    shards: list[dict] = [{} for _ in range(n)]
    for mid, row in entries.items():
        key = row.get("search_key") or mid[: mid.rfind("#")]
        shards[fnv1a(key) % n][mid] = row

    shared_in = sum(1 for v in seen_in.values() if len(v) > 1)
    carried = sum(1 for v in seen_in.values() if v == ["(already shared)"])
    if carried:
        print(f"carried forward   {carried:,} entries from the existing shared set")
    print(f"corpora            {', '.join(d.name for d in corpora)}")
    print(f"distinct entries   {len(entries):,}")
    print(f"in >1 corpus       {shared_in:,}  ({100*shared_in/len(entries):.1f}%)")
    print(f"shared shards      {n}")

    if args.dry_run:
        print("\n(dry run — nothing written)")
        return 0

    # REFUSE A PARTIAL REBUILD. `--rebuild` discards the carried set, so every
    # corpus must have private shards to contribute — and a corpus loses its
    # shards the moment it is shared. Rebuilding two of six and re-sharing
    # therefore drops the other four silently: the payload still builds, the
    # gates still pass, and 28,727 entries with every curated gloss among them
    # are simply gone. That has happened twice.
    if args.rebuild:
        empty = [d.name for d in corpora if not list((d / "lex").glob("surface-*.json"))]
        if empty:
            raise SystemExit(
                "--rebuild needs every corpus built first; these have no shards "
                "of their own:\n  " + "\n  ".join(empty) +
                "\n\nRun pipeline/build.py for each, then share again."
            )

    out = DATA / "lexicon"
    shared_counts: dict[str, int] = {}
    # Read the existing shared sets BEFORE the directory is removed below —
    # same idempotency point as the surface entries, and easy to get wrong
    # because the merge that uses them happens after.
    carried = {
        stem: collect_named(corpora, stem, None if args.rebuild else out)
        for stem in ("classical", "lane", "lisan")
    }
    if out.exists():
        shutil.rmtree(out)
    out.mkdir(parents=True)
    after = 0
    for i, shard in enumerate(shards):
        p = out / f"surface-{i:03d}.json"
        p.write_text(json.dumps(shard, ensure_ascii=False), encoding="utf-8")
        after += p.stat().st_size

    # Lane and the classical index travel with the surface entries: same
    # reasoning, and a word in one book must resolve to the same dictionary
    # entry as the same word in another.
    for stem, merged in carried.items():
        if not merged:
            continue
        k = shard_count(merged, lambda x: x)
        buckets: list[dict] = [{} for _ in range(k)]
        for key, val in merged.items():
            buckets[fnv1a(key) % k][key] = val
        for i, bucket in enumerate(buckets):
            (out / f"{stem}-{i:03d}.json").write_text(
                json.dumps(bucket, ensure_ascii=False), encoding="utf-8")
        shared_counts[stem] = k
        print(f"shared {stem:<10} {len(merged):,} entries in {k} shards")

    # Point each corpus at the shared set and drop its private copy.
    # A version for the shared set, so its URLs change when its contents do.
    #
    # The shared shards are fetched WITHOUT the per-corpus buildId — that is
    # deliberate, so switching books does not re-download a lexicon the reader
    # already has. But a stable URL with no version is a URL that never
    # updates: a reader who visited before a rebuild kept the old entries, and
    # the words they clicked showed the old roots and glosses while the text
    # around them was current.
    digest = hashlib.sha256(
        json.dumps(entries, ensure_ascii=False, sort_keys=True).encode("utf-8")
    ).hexdigest()[:12]
    print(f"shared version     {digest}")

    for d in corpora:
        idx_path = d / "index.json"
        idx = json.loads(idx_path.read_text(encoding="utf-8"))
        idx["shards"]["sharedSurface"] = n
        idx["shards"]["lexiconVersion"] = digest
        for stem, k in shared_counts.items():
            idx["shards"][f"shared{stem.capitalize()}"] = k
        idx_path.write_text(json.dumps(idx, ensure_ascii=False), encoding="utf-8")
        for stem in ("surface", *shared_counts):
            for f in (d / "lex").glob(f"{stem}-*.json"):
                f.unlink()

    # `before` counts only the private shards still on disk, so on a re-run —
    # when most corpora were shared already — it is not the pre-sharing total
    # and a percentage computed from it is nonsense. Report the duplication
    # avoided instead, which is well defined either way.
    dup = sum(len(v) - 1 for v in seen_in.values() if len(v) > 1)
    print(f"\nshared set         {after/1e6:.1f} MB, {len(entries):,} entries")
    print(f"copies avoided     {dup:,} duplicate entries across corpora")
    print(f"wrote {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
