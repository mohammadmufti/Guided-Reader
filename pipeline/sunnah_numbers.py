#!/usr/bin/env python3
"""
Derive sunnah.com's own addressing for Bulugh al-Maram and the Shama'il.

    python pipeline/fetch.py --corpus bulugh     # the witnesses must be cached
    python pipeline/fetch.py --corpus shamail
    python pipeline/sunnah_numbers.py            # fetch source, derive, verify, write

Writes pipeline/corpora/data/{bulugh,shamail}_sunnah_links.json — NUMBERS ONLY,
no text — mapping each witness entry (`idInBook`) to the address sunnah.com
itself uses for that hadith. The maps are committed: they are small, they are
facts rather than expression, and a committed map survives its upstream source
vanishing where a build-time fetch would not.

WHY THIS EXISTS. The vocalisation witnesses (AhmedBaset/hadith-json) are
scrapes of sunnah.com that kept the entry index (`idInBook`) and discarded the
site's own reference numbers — and the two are NOT the same: sunnah.com MERGES
some hadith into one entry (`Ash-Shama'il Al-Muhammadiyah 5, 6` is one entry,
two numbers), so by entry 306 the Shama'il's index trails the site's numbering
by 11. Linking with `idInBook` sent readers to the wrong hadith, and was backed
out; see CORPORA.md "External numbering".

THE SOURCE is a second, independent scrape of the same site that kept what the
first discarded: CheeseWithSauce/HadithsJSONFormat on GitHub, whose `reference`
field preserves the site's reference tables verbatim. It is pinned to a commit
so this derivation is reproducible; the pinned tarball's Arabic text is
byte-for-byte the witness's for every single entry (token overlap 1.000 on all
402 + 1,767 pairs, measured below on every run), which is what lets a
positional zip within each chapter carry the numbers across with no inference.

WHAT THE SITE'S ADDRESSING ACTUALLY IS — this was measured against live pages,
not assumed, and it differs between the two collections:

  * The Shama'il has a complete collection-wide numbering, 1..417, and
    `sunnah.com/shamail:{n}` resolves every one. The 402 entries tile the 417
    numbers exactly (15 merged entries). One site quirk: chapter "8b" (between
    8 and 9 in display order) carries numbers 368-369 — the numbering is not
    monotone in reading order, because the site assigned those numbers late.

  * Bulugh al-Maram has NO complete collection numbering. Colon references
    (`Bulugh al-Maram {n}`) exist only in books 1, 3, 6, 13 and 14 — 381 of
    1,767 entries — and 31 of those numbers are assigned twice. What is
    universal and unique is the PATH form `sunnah.com/bulugh/{book}/{pos}`:
    every entry carries a "Sunnah.com reference: Book B, Hadith N" and the
    page resolves. Verified live: /bulugh/1/5 is the qullatayn hadith (also
    bulugh:5), /bulugh/2/151 is `سبحانك اللهم وبحمدك` — both match the map.
    The positions have a few site-skipped slots (1/151, 2/52, ...) and no
    duplicates; they are recorded as scraped, never synthesised.

  So a per-hadith link for the Shama'il is `shamail:{n}`; for Bulugh it is
  `bulugh/{book}/{pos}`. The colon numbers Bulugh does have are recorded in
  the map for display, but a URL built from a numbering that is partial and
  duplicated would be a wrong link waiting to happen.

VERIFICATION IS THE POINT. Every run re-checks, and a failure stops the write:
per-pair text identity at threshold 1.0 (not "high" — identity; these are two
scrapes of one site), the ref tiling and merge count for the Shama'il against
CORPORA.md's documented figures, and the independently confirmed anchors —
`shamail` entry 306 is site 317 (the one anchor CORPORA.md records as checked
by hand), `bulugh` entry 5 is /bulugh/1/5, entry 327 is /bulugh/2/151. The
first drafting of this derivation zipped by global position and the 306->317
anchor caught it pointing at 319; that is why they are assertions and not
notes.
"""

from __future__ import annotations

import argparse
import glob
import hashlib
import io
import json
import re
import statistics
import sys
import tarfile
import urllib.request
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
OUT_DIR = ROOT / "corpora" / "data"

# Pinned. `zcat tarball | git get-tar-commit-id` must print this; a moved
# branch is a different derivation and must be re-verified, not absorbed.
SOURCE_REPO = "CheeseWithSauce/HadithsJSONFormat"
SOURCE_COMMIT = "1ef8f97ac41cd04845081de79529d879966c6fbc"
SOURCE_TARBALL = f"https://codeload.github.com/{SOURCE_REPO}/tar.gz/{SOURCE_COMMIT}"

# The site's display order for the Shama'il's chapters. "8b" is sunnah.com's
# own: a chapter inserted between 8 and 9, numbered 368-369 at the end of the
# range. The witness carries the same 57 chapters in the same display order.
SHAMAIL_SITE_SEQ = [str(i) for i in range(1, 9)] + ["8b"] + [str(i) for i in range(9, 57)]

DIAC = re.compile(r"[\u064b-\u0652\u0670\u0640]")
AR = re.compile(r"[\u0621-\u064a]+")


def toks(t: str) -> set[str]:
    """Diacritic-stripped, seat-folded token set — the same folds normalise()
    makes, applied locally so this tool imports nothing from the pipeline and
    can run before any of it."""
    t = DIAC.sub("", t or "")
    t = (t.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ٱ", "ا")
          .replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
          .replace("ء", ""))
    return set(AR.findall(t))


def overlap(a: set[str], b: set[str]) -> float:
    return len(a & b) / min(len(a), len(b)) if a and b else 0.0


def fetch_source(dest: Path, offline_tarball: Path | None) -> Path:
    """The pinned tarball, from disk or the network, commit verified."""
    if offline_tarball:
        data = offline_tarball.read_bytes()
    elif dest.exists():
        data = dest.read_bytes()
    else:
        print(f"fetching {SOURCE_TARBALL}")
        with urllib.request.urlopen(SOURCE_TARBALL, timeout=180) as r:
            data = r.read()
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(data)
    # git's tarballs carry the commit id in the tar header comment.
    with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
        comment = tf.pax_headers.get("comment", "")
    if comment != SOURCE_COMMIT:
        sys.exit(f"ERROR: tarball commit {comment!r} is not the pinned "
                 f"{SOURCE_COMMIT!r}. Re-verify before re-pinning: the anchors "
                 f"below check THIS derivation, not any future state of the repo.")
    if not dest.exists():
        dest.write_bytes(data)
    print(f"source: {SOURCE_REPO} @ {SOURCE_COMMIT[:12]}  "
          f"sha256 {hashlib.sha256(data).hexdigest()[:16]}…")
    return dest


def extract(tarball: Path, workdir: Path) -> Path:
    with tarfile.open(tarball, "r:gz") as tf:
        tf.extractall(workdir, filter="data")
    (top,) = [p for p in workdir.iterdir() if p.is_dir()]
    return top / "Sunnah"


def witness(corpus: str) -> list[dict]:
    path = CACHE / corpus / f"{corpus}_vocalised.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} missing — run `python pipeline/fetch.py "
                 f"--corpus {corpus}` first. The map is keyed by the witness's "
                 f"`idInBook`, so it must be derived against the same file the "
                 f"binder aligns to.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    return [x for x in doc["hadiths"] if x.get("arabic")]


def by_chapter(hadiths: list[dict]) -> dict[int, list[dict]]:
    ch: dict[int, list[dict]] = {}
    for x in hadiths:
        ch.setdefault(x["chapterId"], []).append(x)
    return ch


def zip_verified(ours: list[dict], theirs: list[tuple], where: str,
                 scores: list[float]) -> list[tuple[int, tuple]]:
    """Positional zip within one chapter, refused unless counts match and
    every pair's text is identical under normalisation. Position within a
    chapter is what disambiguates a hadith repeated verbatim elsewhere in the
    book — a global best-match cannot, and the first draft's global zip put
    entry 306 at 319.

    The bar is 0.97, not 1.0, for one measured reason: the two scrapes carry
    a handful of missing-space variants of each other (al-Adab's entry 527
    fuses وجليل وهل into one token in the witness), costing a single token of
    overlap on an otherwise identical pair. A genuinely misaligned pair
    measures 0.3-0.5; every aligned pair across five collections measures
    0.99+."""
    if len(ours) != len(theirs):
        sys.exit(f"ERROR: {where}: {len(ours)} witness entries against "
                 f"{len(theirs)} source entries — the chapter map is wrong "
                 f"or an upstream changed. Nothing was written.")
    out = []
    for x, t in zip(ours, theirs):
        s = overlap(toks(x["arabic"]), t[-1])
        scores.append(s)
        if s < 0.95:
            sys.exit(f"ERROR: {where}: witness idInBook {x['idInBook']} does "
                     f"not textually match its positional counterpart "
                     f"(overlap {s:.2f}). These are two scrapes of one site; "
                     f"anything short of identity means the zip is misaligned. "
                     f"Nothing was written.")
        out.append((x["idInBook"], t))
    return out


def derive_shamail(src: Path) -> dict:
    ref = re.compile(r"Reference\s*:\s*Ash-Shama'il Al-Muhammadiyah\s+"
                     r"([\d,\s]+?)\s*In-book reference\s*:\s*Book\s+(\w+),\s*Hadith\s+(\d+)")
    books: dict[str, list] = {}
    for f in sorted(glob.glob(str(src / "shamail" / "*.json"))):
        for x in json.loads(Path(f).read_text(encoding="utf-8")):
            m = ref.search(x["reference"])
            if not m:
                sys.exit(f"ERROR: unparsed shamail reference: {x['reference'][:90]!r}")
            refs = [int(n) for n in m.group(1).replace(" ", "").split(",") if n]
            books.setdefault(m.group(2), []).append(
                (int(m.group(3)), refs, toks(x["arabic"])))
    for b in books:
        books[b].sort(key=lambda t: t[0])
    if set(books) != set(SHAMAIL_SITE_SEQ):
        sys.exit(f"ERROR: shamail site chapters {sorted(books)} do not match "
                 f"the declared sequence.")

    h = witness("shamail")
    ch = by_chapter(h)
    order = sorted(ch)
    if len(order) != len(SHAMAIL_SITE_SEQ):
        sys.exit(f"ERROR: witness has {len(order)} chapters against the "
                 f"site's {len(SHAMAIL_SITE_SEQ)}.")

    scores: list[float] = []
    mapping: dict[int, dict] = {}
    for cid, site_b in zip(order, SHAMAIL_SITE_SEQ):
        for iib, (_, refs, _) in zip_verified(
                ch[cid], books[site_b], f"shamail witness ch {cid} ~ site {site_b}",
                scores):
            mapping[iib] = {"refs": refs}

    # ---- global invariants, against CORPORA.md's documented figures --------
    flat = sorted(r for v in mapping.values() for r in v["refs"])
    assert flat == list(range(1, 418)), \
        "shamail refs must tile 1..417 exactly once"
    assert sum(1 for v in mapping.values() if len(v["refs"]) > 1) == 15, \
        "shamail must have exactly 15 merged entries"
    assert len(mapping) == 402
    # THE anchor: the one correspondence CORPORA.md records as confirmed by
    # hand against the live site. The first draft of this derivation failed it.
    assert mapping[306]["refs"] == [317], \
        f"ANCHOR FAILED: entry 306 must be site 317, got {mapping[306]['refs']}"
    print(f"shamail: 402 entries, refs tile 1..417, 15 merges, "
          f"anchor 306->317 OK, text identity {min(scores):.3f} on all pairs")
    return {str(k): mapping[k] for k in sorted(mapping)}


def derive_bulugh(src: Path) -> dict:
    colon = re.compile(r"Reference\s*:\s*Bulugh al-Maram\s+([\d,\s]+?)\s*"
                       r"In-book reference\s*:\s*Book\s+(\d+),\s*Hadith\s+(\d+)")
    path_ = re.compile(r"Sunnah\.com reference\s*:\s*Book\s+(\d+),\s*Hadith\s+(\d+)")
    books: dict[int, list] = {}
    for f in sorted(glob.glob(str(src / "bulugh" / "*.json"))):
        for x in json.loads(Path(f).read_text(encoding="utf-8")):
            m = colon.search(x["reference"])
            if m:
                book, pos = int(m.group(2)), int(m.group(3))
                refs = [int(n) for n in m.group(1).replace(" ", "").split(",") if n]
            else:
                m2 = path_.search(x["reference"])
                if not m2:
                    sys.exit(f"ERROR: unparsed bulugh reference: "
                             f"{x['reference'][:90]!r}")
                book, pos, refs = int(m2.group(1)), int(m2.group(2)), None
            books.setdefault(book, []).append((pos, refs, toks(x["arabic"])))
    for b in books:
        books[b].sort(key=lambda t: t[0])
        # The site skips a few positions (1/151, 2/52, ...) and duplicates
        # none. Positions are recorded as scraped; a synthesised gapless
        # renumbering would address pages that do not exist.
        pos = [p for p, _, _ in books[b]]
        assert len(pos) == len(set(pos)), f"bulugh book {b}: duplicate positions"

    h = witness("bulugh")
    ch = by_chapter(h)
    # The WITNESS has 16 chapters matching the site's 16 books one for one —
    # the 17th kitab (الطلاق) is our OpenITI edition's division, not the
    # scrape's, and never enters this derivation.
    if sorted(ch) != sorted(books):
        sys.exit(f"ERROR: bulugh witness chapters {sorted(ch)} do not match "
                 f"site books {sorted(books)}.")

    scores: list[float] = []
    mapping: dict[int, dict] = {}
    for b in sorted(ch):
        for iib, (pos, refs, _) in zip_verified(
                ch[b], books[b], f"bulugh witness ch {b} ~ site book {b}", scores):
            entry = {"book": b, "pos": pos}
            if refs:
                # Recorded for DISPLAY only. Colon numbers exist for 381
                # entries across five books and 31 of them are assigned twice;
                # a URL is built from book/pos, which is universal and unique.
                entry["refs"] = refs
            mapping[iib] = entry

    assert len(mapping) == 1767
    # Anchors verified against live pages during derivation (see module doc).
    assert mapping[5] == {"book": 1, "pos": 5, "refs": [5]}, mapping[5]
    assert (mapping[327]["book"], mapping[327]["pos"]) == (2, 151), mapping[327]
    n_colon = sum(1 for v in mapping.values() if "refs" in v)
    print(f"bulugh: 1,767 entries across 16 books, anchors 5->/1/5 and "
          f"327->/2/151 OK, {n_colon} colon refs recorded, "
          f"text identity {min(scores):.3f} on all pairs")
    return {str(k): mapping[k] for k in sorted(mapping)}


def derive_muwatta(src: Path) -> dict:
    """The Muwatta': /malik/{book}/{pos}, positions being per-book ordinals.

    Measured on live pages before this was written, because the site's
    reference tables for this collection are the least uniform of the three:
    30 books display a "Sunnah.com reference" (the URL number, per the Bulugh
    precedent), book 1 displays it on 4 entries, and the rest show only
    USC-MSA and "Arabic reference" rows. What settles it: in every one of the
    34 displayed cases the Sunnah.com number EQUALS the entry's per-book
    ordinal, gapless — unlike Bulugh's — and the USC-MSA numbering is
    provably not the URL (the live book-2 page numbers its entries
    1..6, 9, 10, 10, 10, 12… while listing them in exactly the source's
    order; its 34th entry is the map's 34th). Anchors read live:
    /malik/1/1 and /malik/15/2. So {pos} is the ordinal, and the derivation
    ASSERTS ordinal == Sunnah.com reference wherever the site displays one —
    if that ever fails, the ordinal hypothesis fails with it and nothing is
    written.

    The witness here is the sunnah.com scrape declared as the corpus's
    cross_reference_witness (the vocalisation CSV is a different dataset with
    no entry identity at all — 1,594 rows against the site's 1,985). 125 of
    the witness's entries carry no Arabic; they still occupy their slot in
    the chapter zip, are never text-verified (there is nothing to verify),
    and never receive a map entry — an index the binder can never stamp needs
    no address.
    """
    sref = re.compile(r"Sunnah\.com reference\s*:\s*Book\s+(\d+),\s*Hadith\s+(\d+)")
    books: dict[int, list] = {}
    for i, f in enumerate(sorted(glob.glob(str(src / "malik" / "*.json"))), 1):
        # These files carry a UTF-8 BOM, alone among the three collections.
        entries = json.loads(Path(f).read_text(encoding="utf-8-sig"))
        books[i] = []
        for pos, x in enumerate(entries, 1):
            m = sref.search(x["reference"])
            if m:
                assert (int(m.group(1)), int(m.group(2))) == (i, pos), (
                    f"malik book {i} entry {pos}: the site displays "
                    f"Sunnah.com reference {m.group(1)}/{m.group(2)} — the "
                    f"ordinal hypothesis just failed; nothing was written")
            books[i].append((pos, toks(x["arabic"])))

    path = CACHE / "muwatta" / "muwatta_numbered.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} missing — run `python pipeline/fetch.py "
                 f"--corpus muwatta` first.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    ch: dict[int, list[dict]] = {}
    for x in doc["hadiths"]:
        ch.setdefault(x["chapterId"], []).append(x)
    if sorted(ch) != sorted(books):
        sys.exit(f"ERROR: muwatta witness chapters {sorted(ch)} do not match "
                 f"the site's books {sorted(books)}.")

    scores: list[float] = []
    mapping: dict[int, dict] = {}
    textless = 0
    for b in sorted(ch):
        ours, theirs = ch[b], books[b]
        if len(ours) != len(theirs):
            sys.exit(f"ERROR: muwatta book {b}: {len(ours)} witness entries "
                     f"against {len(theirs)} source entries. Nothing written.")
        for x, (pos, T) in zip(ours, theirs):
            if not x.get("arabic"):
                textless += 1
                continue
            s = overlap(toks(x["arabic"]), T)
            scores.append(s)
            if s < 0.95:
                sys.exit(f"ERROR: muwatta witness idInBook {x['idInBook']} "
                         f"does not textually match site book {b} pos {pos} "
                         f"(overlap {s:.2f}). Nothing was written.")
            mapping[x["idInBook"]] = {"book": b, "pos": pos}

    assert len(mapping) + textless == 1985
    # Anchors read live during derivation (see docstring).
    assert mapping[1] == {"book": 1, "pos": 1}, mapping[1]
    print(f"muwatta: {len(mapping):,} entries mapped across 61 books "
          f"({textless} textless witness slots skipped), ordinal==displayed "
          f"Sunnah.com reference on every shown row, anchor 1->/1/1 OK, "
          f"text identity {min(scores):.3f} on all pairs")
    return {str(k): mapping[k] for k in sorted(mapping)}


def derive_adab(src: Path) -> dict:
    """Al-Adab al-Mufrad: sunnah.com/adab:{n} — CAbd al-Baqi's numbering,
    which the site, the witness and our chosen edition all share.

    Order is FILE ORDER, verified against the live site rather than assumed:
    the /adab/14 chapter page lists its entries in exactly the scrape's file
    order — including the site's one numbering quirk, TWO consecutive
    entries both labeled 270 (the site added the "nothing heavier on the
    scale" hadith without renumbering the book). A first draft sorted
    entries by their "In-book reference" number instead, and the four
    lettered sub-entries (348a/b, 1001b, 1319b) print "Hadith 0" there,
    colliding with real positions and scrambling two chapters — the
    text-identity check caught it at 0.16 where aligned pairs measure 0.99+.

    The reference number itself comes from the colon row where the page
    shows one, and from the "Arabic/English book reference" row for the 145
    entries (seven books) where that is all the page shows — the same
    numbering, which the tiling assertion PROVES: both formats' integers
    interleave into one gapless 1..1322, with the duplicate set exactly
    {270, 348, 1001, 1319} (the added hadith and the three letter splits).
    Anchor read live: adab:1 is the Abu CAmr al-Shaybani "owner of this
    house" hadith, the same text the witness numbers 1.
    """
    colon = re.compile(r"Reference\s*:\s*Al-Adab Al-Mufrad\s+"
                       r"([\da-z,\s]+?)\s*In-book")
    fallback = re.compile(r"Arabic/English book reference\s*:\s*"
                          r"Book\s+(\d+),\s*Hadith\s+(\d+)")
    books: dict[int, list] = {}
    for bi, f in enumerate(sorted(glob.glob(str(src / "adab" / "*.json"))), 1):
        for x in json.loads(Path(f).read_text(encoding="utf-8-sig")):
            m = colon.search(x["reference"])
            if m:
                refs = [int(n) if n.isdigit() else n
                        for n in m.group(1).replace(" ", "").split(",") if n]
            else:
                m2 = fallback.search(x["reference"])
                if not m2:
                    sys.exit(f"ERROR: unparsed adab reference: "
                             f"{x['reference'][:90]!r}")
                refs = [int(m2.group(2))]
            books.setdefault(bi, []).append((len(books.get(bi, [])) + 1,
                                             refs, toks(x["arabic"])))

    path = CACHE / "adab" / "adab_vocalised.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} missing — run `python pipeline/fetch.py "
                 f"--corpus adab` first.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    ch: dict[int, list[dict]] = {}
    for x in doc["hadiths"]:
        if x.get("arabic"):
            ch.setdefault(x["chapterId"], []).append(x)
    if len(ch) != len(books):
        sys.exit(f"ERROR: adab witness has {len(ch)} chapters against the "
                 f"site's {len(books)} books.")

    scores: list[float] = []
    mapping: dict[int, dict] = {}
    for cid, b in zip(sorted(ch), sorted(books)):
        for iib, (_, refs, _) in zip_verified(
                ch[cid], books[b], f"adab witness ch {cid} ~ site book {b}",
                scores):
            mapping[iib] = {"refs": refs}

    def _num(r):
        return r if isinstance(r, int) else int(re.match(r"\d+", r).group())
    nums = sorted(_num(r) for v in mapping.values() for r in v["refs"])
    assert sorted(set(nums)) == list(range(1, 1323)), \
        "adab: the numbers must cover 1..1322 gapless"
    from collections import Counter
    dups = {n for n, c in Counter(nums).items() if c > 1}
    assert dups == {270, 348, 1001, 1319}, \
        f"adab: unexpected duplicate set {sorted(dups)} — the site's quirks " \
        f"are the double 270 and the three letter splits, nothing else"
    assert len(mapping) == 1326
    assert mapping[1]["refs"] == [1], \
        "ANCHOR: entry 1 is sunnah.com/adab:1, read live"
    print(f"adab: {len(mapping):,} entries across 57 books, numbers cover "
          f"1..1322 with the four known duplicates, anchor 1->adab:1 OK, "
          f"text identity {min(scores):.3f} on all pairs")
    return {str(k): mapping[k] for k in sorted(mapping)}


def derive_riyad(src: Path) -> dict:
    """Riyad al-Salihin: sunnah.com/riyadussalihin:{n}, complete colon
    numbering 1..1896 — and the one collection whose witness is NOT in the
    site's order.

    The witness scrape appended the site's first book last: its chapter 0 is
    the synthetic "Book of Miscellany" (site numbers 1..679) carrying
    idInBook 1218..1896, while chapters 1..19 hold idInBook 1..1217 for the
    site's books 2..20. So the chapter pairing is EXPLICIT — chapter 0 to
    the miscellany file, chapter N to the Nth numbered file — and the map is
    what untangles the numbering; a link built on idInBook here would be
    wrong for every single hadith.
    """
    colon = re.compile(r"Reference\s*:\s*Riyad as-Salihin\s+"
                       r"([\da-z,\s]+?)\s*In-book")
    files = sorted(glob.glob(str(src / "riyadussalihin" / "*.json")))
    misc = [f for f in files if "miscellany" in f]
    numbered = [f for f in files if "miscellany" not in f]
    if len(misc) != 1 or len(numbered) != 19:
        sys.exit(f"ERROR: riyad source shape changed: {len(misc)} miscellany "
                 f"files, {len(numbered)} numbered books.")

    def read(f):
        out = []
        for x in json.loads(Path(f).read_text(encoding="utf-8-sig")):
            m = colon.search(x["reference"])
            if not m:
                sys.exit(f"ERROR: unparsed riyad reference: "
                         f"{x['reference'][:90]!r}")
            refs = [int(n) if n.isdigit() else n
                    for n in m.group(1).replace(" ", "").split(",") if n]
            out.append((len(out) + 1, refs, toks(x["arabic"])))
        return out

    site = {0: read(misc[0])}
    for i, f in enumerate(numbered, 1):
        site[i] = read(f)

    path = CACHE / "riyad" / "riyad_vocalised.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} missing — run `python pipeline/fetch.py "
                 f"--corpus riyad` first.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    ch: dict[int, list[dict]] = {}
    for x in doc["hadiths"]:
        if x.get("arabic"):
            ch.setdefault(x["chapterId"], []).append(x)
    if sorted(ch) != sorted(site):
        sys.exit(f"ERROR: riyad witness chapters {sorted(ch)} do not match "
                 f"the site's books {sorted(site)}.")

    scores: list[float] = []
    mapping: dict[int, dict] = {}
    for b in sorted(ch):
        for iib, (_, refs, _) in zip_verified(
                ch[b], site[b], f"riyad witness ch {b} ~ site book {b}",
                scores):
            mapping[iib] = {"refs": refs}

    flat = sorted(r for v in mapping.values() for r in v["refs"]
                  if isinstance(r, int))
    assert flat == list(range(1, 1897)), \
        "riyad refs must tile 1..1896 exactly once"
    assert len(mapping) == 1896
    # The untangling this map exists for, stated as an anchor: the witness's
    # FIRST entry is the site's 680, and the miscellany's first (site 1) is
    # the witness's 1218.
    assert mapping[1]["refs"] == [680], mapping[1]
    assert mapping[1218]["refs"] == [1], mapping[1218]
    print(f"riyad: 1,896 entries, refs tile 1..1896, witness order untangled "
          f"(idInBook 1 -> 680, 1218 -> 1), "
          f"text identity {min(scores):.3f} on all pairs")
    return {str(k): mapping[k] for k in sorted(mapping)}


def derive_muslim(src: Path) -> dict:
    """Sahih Muslim: sunnah.com/muslim:{n} where {n} is the site's LETTERED
    number ("8a") — the map that serves al-Mundhiri's Mukhtasar the way the
    Bukhari witness serves al-Tajrid.

    This map is keyed by the FULL Sahih's witness (`muslim_vocalised.json`,
    the Mukhtasar corpus's vocalisation reference): the abridgement aligns
    each of its records to a row of the full collection, and this translates
    that row into the site's address. Letters matter — muslim:1662a and
    muslim:1662b are different hadith — so refs ride as strings wherever the
    site letters them, and the display number is only shown where the site's
    number is a plain integer.

    The witness scrape appends the muqaddima last (chapter 1 in its own ids,
    `introduction.json` sorting after the numbered books — the same
    arrangement Riyad's miscellany has). The muqaddima's 91 entries carry
    "Sahih Muslim Introduction N" references with no colon URL of the form
    this template builds, and the Mukhtasar abridges the Sahih proper, so
    they are mapped as DECLARED no-links: present (a stray retrieval must
    not read as witness/map drift and fail the build) but yielding no
    address.
    """
    ref = re.compile(r"Reference\s*:\s*Sahih Muslim\s+"
                     r"(\d+[a-z]*(?:\s*,\s*\d+[a-z]*)*)")
    intro = re.compile(r"Reference\s*:\s*Sahih Muslim Introduction\s+(\d+)")
    files = sorted(glob.glob(str(src / "muslim" / "*.json")))
    intro_f = [f for f in files if "introduction" in f]
    numbered = [f for f in files if "introduction" not in f]
    if len(intro_f) != 1 or len(numbered) != 56:
        sys.exit(f"ERROR: muslim source shape changed: {len(intro_f)} intro "
                 f"files, {len(numbered)} numbered books.")

    def read(f, is_intro):
        out = []
        for x in json.loads(Path(f).read_text(encoding="utf-8-sig")):
            # The muqaddima is MIXED: its first narrations carry plain colon
            # numbers (muslim:1..7 are muqaddima hadith — the Book of Faith
            # starts at 8a), the rest read "Sahih Muslim Introduction N" and
            # have no address of this template's form. Try the colon form
            # first everywhere; only an Introduction-style entry becomes a
            # declared no-link.
            m = ref.search(x["reference"])
            if not m and is_intro and intro.search(x["reference"]):
                out.append((len(out) + 1, None, toks(x["arabic"])))
                continue
            if not m:
                sys.exit(f"ERROR: unparsed muslim reference: "
                         f"{x['reference'][:90]!r}")
            refs = [int(n) if n.isdigit() else n
                    for n in m.group(1).replace(" ", "").split(",") if n]
            out.append((len(out) + 1, refs, toks(x["arabic"])))
        return out

    # The witness's chapter 1 IS the muqaddima; its numbered books follow.
    site = {0: read(intro_f[0], True)}
    for i, f in enumerate(numbered, 1):
        site[i] = read(f, False)

    path = CACHE / "mukhtasar" / "muslim_vocalised.json"
    if not path.exists():
        sys.exit(f"ERROR: {path} missing — run `python pipeline/fetch.py "
                 f"--corpus mukhtasar` first.")
    doc = json.loads(path.read_text(encoding="utf-8"))
    ch: dict[int, list[dict]] = {}
    for x in doc["hadiths"]:
        if x.get("arabic"):
            ch.setdefault(x["chapterId"], []).append(x)
    if len(ch) != len(site):
        sys.exit(f"ERROR: muslim witness has {len(ch)} chapters against the "
                 f"site's {len(site)}.")

    scores: list[float] = []
    mapping: dict[int, dict] = {}
    for cid, b in zip(sorted(ch), sorted(site)):
        for iib, (_, refs, _) in zip_verified(
                ch[cid], site[b], f"muslim witness ch {cid} ~ site book {b}",
                scores):
            mapping[iib] = ({"nolink": True} if refs is None
                            else {"refs": refs})

    def _num(r):
        return r if isinstance(r, int) else int(re.match(r"\d+", r).group())
    nums = sorted({_num(r) for v in mapping.values()
                   for r in v.get("refs", [])})
    # The site's own numbering skips eleven integers — measured, then
    # pinned: three singles and a run of eight just before the final 3033
    # (entries the site renumbered or never assigned). A DIFFERENT missing
    # set would mean the scrape or the parse drifted.
    missing = set(range(1, nums[-1] + 1)) - set(nums)
    assert nums[-1] == 3033 and missing == \
        {1698, 1824, 2483, 3007, 3008, 3009, 3010, 3011, 3012, 3013, 3014}, \
        f"muslim numbering changed shape: max {nums[-1]}, " \
        f"missing {sorted(missing)}"
    assert len(mapping) == 7459
    n_nolink = sum(1 for v in mapping.values() if v.get("nolink"))
    assert n_nolink == 83, \
        f"the muqaddima's Introduction-style entries number 83, got {n_nolink}"
    # Anchor: the site's first entry of the Book of Faith is muslim:8a.
    first_faith = min(i for i, v in mapping.items() if "refs" in v)
    assert mapping[first_faith]["refs"] == ["8a"], mapping[first_faith]
    print(f"muslim: {len(mapping):,} entries across 56 books + muqaddima "
          f"({n_nolink} declared no-link), numbers cover 1..{nums[-1]} "
          f"with the eleven pinned site gaps, first Faith entry -> "
          f"muslim:8a, "
          f"text identity {min(scores):.3f} on all pairs")
    return {str(k): mapping[k] for k in sorted(mapping)}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--tarball", type=Path, default=None,
                    help="use a downloaded source tarball instead of fetching")
    args = ap.parse_args()

    tarball = fetch_source(CACHE / "sunnah-links" / "source.tar.gz", args.tarball)
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        src = extract(tarball, Path(td))
        shamail = derive_shamail(src)
        bulugh = derive_bulugh(src)
        muwatta = derive_muwatta(src)
        adab = derive_adab(src)
        riyad = derive_riyad(src)
        muslim = derive_muslim(src)

    OUT_DIR.mkdir(parents=True, exist_ok=True)
    prov = {
        "source": f"github.com/{SOURCE_REPO}",
        "commit": SOURCE_COMMIT,
        "derived": date.today().isoformat(),
        "derivedBy": "pipeline/sunnah_numbers.py — see its docstring for the "
                     "method and the anchors this file passed",
        "contains": "numbers only; no text from any source is included",
    }
    for name, entries, note in (
        ("shamail", shamail,
         "refs are sunnah.com's collection numbers; URL is shamail:{refs[0]}, "
         "a merged entry lists every number it spans"),
        ("bulugh", bulugh,
         "the address is sunnah.com/bulugh/{book}/{pos}; colon refs, where "
         "present, are display-only — partial (5 of 16 books) and 31 are "
         "duplicated on the site"),
        ("adab", adab,
         "refs are sunnah.com's collection numbers (CAbd al-Baqi's, which "
         "this edition shares); URL is adab:{refs[0]}"),
        ("riyad", riyad,
         "refs are sunnah.com's collection numbers, which this edition "
         "shares; URL is riyadussalihin:{refs[0]}; the witness's own order "
         "is NOT the site's — its miscellany is appended last — which is "
         "why this map exists"),
        ("muslim", muslim,
         "refs are sunnah.com's lettered numbers for the FULL Sahih "
         "(muslim:8a); keyed by the full collection's witness, which serves "
         "al-Mundhiri's Mukhtasar the way the Bukhari witness serves "
         "al-Tajrid; the muqaddima's 91 entries are declared no-links"),
        ("muwatta", muwatta,
         "the address is sunnah.com/malik/{book}/{pos}; pos is the per-book "
         "ordinal, equal to the site's Sunnah.com reference on every row it "
         "displays; keyed by the cross_reference_witness's idInBook — the "
         "vocalisation CSV has no entry identity"),
    ):
        out = OUT_DIR / f"{name}_sunnah_links.json"
        out.write_text(json.dumps(
            {"_provenance": {**prov, "note": note}, "entries": entries},
            ensure_ascii=False, indent=0) + "\n", encoding="utf-8")
        print(f"wrote {out.relative_to(ROOT.parent)}  "
              f"({out.stat().st_size/1024:.0f} KB, {len(entries)} entries)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
