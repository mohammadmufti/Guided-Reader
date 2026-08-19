#!/usr/bin/env python3
"""
Ingest Ibn Manẓūr's *Lisān al-ʿArab* into structured entries, keyed by root.

    python pipeline/fetch.py --corpus lisan
    python pipeline/lisan.py            # mARkdown -> build/lisan/entries.json

WHY THIS EXISTS. Lane's Lexicon answers in English and stops at 5,078 roots.
This answers in Arabic across 8,974, and it is the book Lane cites as `L`. A
student who has spent a month reading `(L)` in Lane's brackets can now open it.

It is deliberately the SAME SHAPE as `lane.py`'s output — root -> entries ->
senses -> runs — so `build.py` links it with the candidate ladder already
written rather than a second one, and the panel renders it with the same
component. Everything below is about the three places this source differs from
Lane, because those are the only places judgement was required.

ONE ARTICLE PER ROOT, NOT PER HEADWORD. Lane files صَلَاةٌ as its own entry
(n24821) under صلو, which is what lets a word be shown ITS OWN entry. Ibn Manẓūr
writes one continuous article per root. So there is no per-headword id to match
and no `laneEntry` analogue: a word resolves to its root's article or to
nothing. The panel must therefore say "the article on the root" and never "this
word's own entry" — claiming the latter would be false for every word here.

`#` LINES ARE NOT PARAGRAPHS. This is the finding that shaped the parser.
Measured across the whole book, 52.5% of `#` units are under 60 characters and
55.5% do not end in terminal punctuation: Shamela breaks lines around block
quotations and verse, mid-sentence. Rendered as-is the ṣalāh article opens

    [1] الصلاة: الركوع والسجود. فأما
    [2] قوله، صلى الله عليه وسلم: لا صلاة لجار المسجد إلا في المسجد
    [3] ، فإنه أراد لا صلاة فاضلة أو كاملة، والجمع صلوات

— one sentence in three pieces, the third starting with a comma. So the article
is REJOINED into continuous prose and then split on sentence enders, which
recovers `الصلاة: الركوع والسجود.` as the opening unit. That is the classical
definition, arriving first, with no ranking heuristic and no sampling.

The units are labelled `level: "sentence"` and carry no label, because Ibn
Manẓūr wrote no sense numbers. Inventing them would be the sampling error this
project already paid for once — see ROADMAP principle 2.

NO HARAKAT, AND NONE INVENTED. Every OpenITI version of this text is fully
undiacritised; all six were checked (JK, ShamAY, Shamela, Shia for Lisān, plus
the Nihāya set) and every one has exactly zero marks. Running a diacritiser over
the entry text is refused on the grounds DIACRITISATION.md §4 already settled:
wrong vowels shown confidently are worse than none. The panel says the text is
unvocalised; that is the whole mitigation and it is the correct one.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from pathlib import Path

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "build" / "lisan"

sys.path.insert(0, str(ROOT))
from corpus import ConfigError, load_config, source_path  # noqa: E402
from normalise import root_key  # noqa: E402
from dictionaries import (  # noqa: E402
    audit,
    dict_root_variants,
    sentences,
)
import lisan_vocalised  # noqa: E402

# Kept as a name so `build.py` and the tests need not change when a helper
# moves. The behaviour is identical and shared: al-Nihaya files final-weak
# roots under a bare alif too — 338 of its roots — which is what turned a
# source-specific rule into a shared one.
lisan_root_variants = dict_root_variants


def compile_strip(cfg: dict) -> list[tuple[str, re.Pattern[str]]]:
    """The strip patterns, in the order the config lists them.

    Order is load-bearing and the config says so: manuscript markers nest
    inside div tags and page brackets, so the nesting marker goes first.
    """
    seg = cfg.get("segmentation") or {}
    out = []
    for spec in seg.get("strip") or []:
        out.append((spec["name"], re.compile(spec["pattern"])))
    return out


def parse(text: str, cfg: dict) -> tuple[dict[str, dict], dict]:
    """
    mARkdown -> {root_key: entry}, plus a counters dict for the report.

    Page and volume are carried from the last `PageV{v}P{p}` seen BEFORE each
    entry head. Those markers sit on their own lines, outside the `#`/`~~` body
    grammar, so they are provenance the body parse would otherwise discard.
    They are worth keeping precisely here: the OpenITI annotator collated this
    digitisation's pagination against the printed Dār Ṣādir edition, so a
    reader can check us against a physical book.
    """
    seg = cfg["segmentation"]
    entry_re = re.compile(seg["entry"])
    para_re = re.compile(seg["paragraph"])
    cont_re = re.compile(seg["continuation"])
    page_re = re.compile(seg["page_marker_alt"])
    strips = compile_strip(cfg)

    counts = {"heads": 0, "unparsed": 0, "with_page": 0, "merged_fragments": 0}
    # The order OpenITI declares entries in. `lisan_vocalised.align` walks
    # this against Shamela's heads; order is what tells a real head from a
    # cross-reference that happens to look identical.
    head_order: list[str] = []

    def clean(s: str) -> str:
        for _, pat in strips:
            s = pat.sub(" ", s)
        return re.sub(r"\s+", " ", s).strip()

    body = text.split("#META#Header#End#", 1)[-1]

    roots: dict[str, dict] = {}
    cur: dict | None = None
    lines: list[str] = []
    last_page: tuple[int, int] | None = None

    def close() -> None:
        """Rejoin, sentence-split, and file the article under way."""
        nonlocal cur, lines
        if cur is None:
            return
        joined = clean(" ".join(lines))
        units = sentences(joined)
        counts["merged_fragments"] += getattr(sentences, "merged", 0)
        if units:
            key = cur["key"]
            senses = [
                {"label": None, "level": "sentence", "runs": [{"t": "ar", "v": u}]}
                for u in units
            ]
            existing = roots.get(key)
            if existing is None:
                roots[key] = {
                    "root": key,
                    "headword": cur["headword"],
                    "vol": cur["vol"],
                    "page": cur["page"],
                    "entries": [
                        {
                            "nodeid": key,
                            "headword": cur["headword"],
                            "itypes": None,
                            "senses": senses,
                        }
                    ],
                }
            else:
                # 178 of 9,152 heads fold onto a root another head already
                # holds — the book files a few articles twice, and root_key
                # folds a few spelling variants together. Append rather than
                # overwrite: dropping one would silently lose an article.
                existing["entries"][0]["senses"].extend(senses)
        cur, lines = None, []

    for line in body.split("\n"):
        page = page_re.search(line)
        if page:
            last_page = (int(page.group(1)), int(page.group(2)))

        head = entry_re.match(line)
        if head:
            close()
            counts["heads"] += 1
            written = head.group(1).strip()
            key = root_key(written)
            if not key:
                counts["unparsed"] += 1
                continue
            # EVERY head, duplicates included. 178 heads fold onto a root
            # another head already holds, and `close()` concatenates their
            # articles. De-duplicating here would align only the first, then
            # compare Shamela's one article against OpenITI's two and reject
            # the entry for a disagreement we manufactured.
            head_order.append(key)
            if last_page:
                counts["with_page"] += 1
            cur = {
                "key": key,
                "headword": written,
                "vol": last_page[0] if last_page else None,
                "page": last_page[1] if last_page else None,
            }
            lines = [head.group(2)]
            continue

        if line.startswith("###"):
            # A structural heading — حرف الهمزة, فصل الباء. Ends the article
            # under way and contributes nothing: it is navigation in a book we
            # are not making navigable, only lookupable.
            close()
            continue

        if cur is None:
            continue
        m = para_re.match(line) or cont_re.match(line)
        if m:
            lines.append(m.group(1))

    close()
    counts["head_order"] = head_order
    return roots, counts


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="lisan")
    ap.add_argument("--roots", default="", help="optional comma-separated root filter")
    ap.add_argument("--no-assert", action="store_true",
                    help="report the figures without checking them against the config")
    args = ap.parse_args()

    try:
        cfg = load_config(args.corpus)
        path = source_path(cfg, "text")
    except ConfigError as e:
        print(e, file=sys.stderr)
        return 1

    text = path.read_text(encoding=cfg["sources"]["text"].get("encoding", "utf-8"))
    roots, counts = parse(text, cfg)

    # ---- swap in Shamela's vocalised text ---------------------------------
    #
    # Structure stays OpenITI's; only the characters change. Every entry is
    # checked against the text it replaces, and one that fails keeps what it
    # had — a doubtful substitute is worse than a bare one, and silently
    # replacing 13 million characters on faith is not something to do because
    # the sample looked right.
    voc_stats = {"aligned": 0, "swapped": 0, "rejected": 0, "absent": 0}
    try:
        bok = source_path(cfg, "vocalised")
    except ConfigError:
        bok = None
    if bok and bok.exists():
        cands = lisan_vocalised.candidate_entries(lisan_vocalised.export_pages(bok))
        matched = lisan_vocalised.align(counts["head_order"], cands)
        voc_stats["aligned"] = len(matched)
        for key, payload in roots.items():
            hit = matched.get(key)
            if hit is None:
                voc_stats["absent"] += 1
                continue
            # SAME strip patterns as the OpenITI path. The Shamela text has
            # its own editorial furniture — «1» footnote references above all —
            # and skipping this leaves `السَّمُّ «2»` in a rendered run.
            joined = re.sub(r"\s+", " ", " ".join(hit["lines"])).strip()
            for _name, _pat in compile_strip(cfg):
                joined = _pat.sub(" ", joined)
            joined = re.sub(r"\s+", " ", joined).strip()
            openiti = " ".join(
                r["v"] for e in payload["entries"] for s_ in e["senses"] for r in s_["runs"]
            )
            score = lisan_vocalised.verify(key, joined, openiti)
            if score < lisan_vocalised.MIN_SIMILARITY:
                voc_stats["rejected"] += 1
                continue
            units = sentences(joined)
            if not units:
                voc_stats["rejected"] += 1
                continue
            payload["entries"][0]["senses"] = [
                {"label": None, "level": "sentence", "runs": [{"t": "ar", "v": u}]}
                for u in units
            ]
            payload["headword"] = hit["written"]
            payload["entries"][0]["headword"] = hit["written"]
            voc_stats["swapped"] += 1
    else:
        print("  (no Shamela .bok — shipping the unvocalised OpenITI text)")

    wanted = {root_key(r) for r in args.roots.split(",") if r}
    if wanted:
        roots = {k: v for k, v in roots.items() if k in wanted}

    problems = audit(roots)

    n_senses = sum(len(e["senses"]) for p in roots.values() for e in p["entries"])
    chars = sum(len(run["v"]) for p in roots.values() for e in p["entries"]
                for s in e["senses"] for run in s["runs"])
    page_share = counts["with_page"] / max(counts["heads"], 1)

    print(f"entry heads       {counts['heads']:>8,}")
    print(f"unique roots      {len(roots):>8,}")
    print(f"sentence units    {n_senses:>8,}   ({n_senses/max(len(roots),1):.1f} per root)")
    print(f"fragments merged  {counts['merged_fragments']:>8,}")
    print(f"unparsed heads    {counts['unparsed']:>8,}")
    print(f"with vol/page     {counts['with_page']:>8,}   ({page_share:.1%})")
    print(f"text              {chars/1e6:>8.1f} M chars")
    print(f"residual markers  {'NONE' if not problems else 'PRESENT':>8}")

    marks = sum(
        1 for p_ in roots.values() for e in p_["entries"] for s_ in e["senses"]
        for r in s_["runs"] for c in r["v"] if unicodedata.category(c).startswith("M")
    )
    letters = sum(
        1 for p_ in roots.values() for e in p_["entries"] for s_ in e["senses"]
        for r in s_["runs"] for c in r["v"] if "\u0621" <= c <= "\u064a"
    )
    if voc_stats["aligned"]:
        print(f"\nvocalised text    {voc_stats['swapped']:>8,} entries swapped from Shamela")
        print(f"  rejected        {voc_stats['rejected']:>8,}   (kept OpenITI: text did not verify)")
        print(f"  unmatched       {voc_stats['absent']:>8,}   (no aligned Shamela entry)")
    print(f"harakat ratio     {marks/max(letters,1):>8.3f}   ({marks:,} marks on {letters:,} letters)")

    floor = (cfg.get("expected") or {}).get("min_harakat_ratio")
    if floor is not None and not args.no_assert and not wanted:
        if marks / max(letters, 1) < floor:
            problems.append(
                f"harakat ratio {marks/max(letters,1):.3f} below floor {floor} — "
                "the vocalised source did not take"
            )

    expected = cfg.get("expected") or {}
    if not args.no_assert and not wanted:
        if expected.get("entry_heads") not in (None, counts["heads"]):
            problems.append(
                f"entry heads {counts['heads']:,} != expected "
                f"{expected['entry_heads']:,} — the source changed under us"
            )
        if expected.get("unique_roots") not in (None, len(roots)):
            problems.append(
                f"unique roots {len(roots):,} != expected {expected['unique_roots']:,}"
            )
        floor = expected.get("min_page_coverage")
        if floor is not None and page_share < floor:
            problems.append(f"vol/page coverage {page_share:.1%} below floor {floor:.0%}")

    if problems:
        print("\nFAILED:", file=sys.stderr)
        for p in problems:
            print(f"  {p}", file=sys.stderr)
        return 1

    OUT.mkdir(parents=True, exist_ok=True)
    out = OUT / "entries.json"
    out.write_text(json.dumps(roots, ensure_ascii=False), encoding="utf-8")
    print(f"\nwrote {out.relative_to(ROOT.parent)}  ({out.stat().st_size/1e6:.1f} MB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
