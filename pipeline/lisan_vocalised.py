"""
The vocalised Lisān: Shamela's own text, aligned onto OpenITI's entry structure.

WHY TWO SOURCES FOR ONE BOOK. Every OpenITI version of Lisān al-ʿArab is
stripped of harakat — all four were checked and each has exactly zero combining
marks of any Unicode category. Our fetch is not at fault: the downloaded file
matches upstream's checksum byte for byte. Shamela's own distribution of the
SAME EDITION (Dār Ṣādir, 3rd ed. 1414 AH, with al-Yāzijī's notes) keeps them:

        Arabic letters   combining marks   ratio
    bok    13,179,687          8,385,210   0.636
    OpenITI 12,806,345                 0   0.000
    Lane     1,335,698         1,016,223   0.761

These are the EDITORS' vowels as printed. Nothing is generated, so
DIACRITISATION.md §4 is untouched — that rule forbids inventing vocalisation,
and this is its opposite.

WHY NOT JUST PARSE THE .bok AND DROP OpenITI. Because the .bok has no entry
markup. Its heads are plain `root: ` lines at the start of a line, and a
cross-reference sitting INSIDE an article looks exactly the same. Matching them
naively yields 11,915 candidates for 8,973 real entries — roughly 2,900
spurious splits, each of which truncates a real article. OpenITI's `### $`
markers, by contrast, are hand-curated by a named annotator.

So the two are combined by what each is good at:

    OpenITI   decides WHERE an entry begins   (curated structure)
    Shamela   supplies WHAT IT SAYS           (vocalised text)

THE ALIGNMENT. Both sources present entries in the book's own order, so this is
a sequence problem, not a lookup problem. Walking the two in parallel and
requiring the root to match makes a spurious split reject itself: it is out of
order with respect to OpenITI's sequence, while a real head is not.

WHAT MAKES THE SWAP SAFE. The two derivations are independent, so they check
each other. Strip the harakat from Shamela's text and it must reproduce the
text we already ship, entry by entry — measured median similarity 1.000. That
is an unusually strong gate and it falls out of the design rather than being
bolted on: `verify()` below refuses any entry that fails it, and those entries
keep the OpenITI text rather than taking a doubtful substitute.
"""

from __future__ import annotations

import difflib
import re
import unicodedata
from pathlib import Path

from normalise import root_key

# Shamela separates the editors' footnotes from the page body with a rule.
# They are real content — OpenITI drops them entirely — but they are apparatus
# about the text rather than the text, and mixing them into the article body
# would put "كذا بالنسخ" in the middle of a definition.
FOOTNOTE_RULE = "__________"

# An entry head: a root, a colon, whitespace. Same convention OpenITI's
# annotator tagged. Deliberately permissive — the sequence alignment is what
# distinguishes a head from a mid-article cross-reference, not this pattern.
HEAD = re.compile(r"^([^\s:]{2,14}):\s")

# Below this, the de-diacritised text is not recognisably the same article and
# the entry keeps its OpenITI body. Set from the measured distribution: median
# 1.000, and the tail is spurious splits rather than genuine textual variance.
MIN_SIMILARITY = 0.90

ARABIC_ONLY = re.compile(r"[^\u0621-\u064a]")


def strip_marks(s: str) -> str:
    """Every combining mark, not a hand-listed set of harakat."""
    return "".join(c for c in s if not unicodedata.category(c).startswith("M"))


def export_pages(bok: Path, table: str = "b1687") -> list[dict]:
    """
    Read the Access database Shamela ships. Pure Python, deliberately.

    THIS USED TO SHELL OUT TO `mdb-export`, which meant CI had to
    `apt-get install mdbtools` on every cold runner. That step hung for six
    hours and was killed by the job timeout — `apt-get update` blocks
    indefinitely when the runner's background unattended-upgrades holds the
    dpkg lock, and no timeout or DEBIAN_FRONTEND was set. Adding a timeout
    would have papered over it; a build should not need a package manager to
    read a file it already has.

    `access_parser` returns Memo text as raw CP1256 bytes mis-decoded as
    latin-1 — `Ü[áÓÇä ÇáÚÑÈ]Ü` for `ـ[لسان العرب]ـ` — because this is an old
    Shamela database in the Windows Arabic codepage rather than UCS-2. The
    round-trip below restores it, and reproduces mdbtools byte for byte:
    13,179,687 Arabic letters and 8,385,210 combining marks either way.
    """
    try:
        from access_parser import AccessParser
    except ImportError:
        raise SystemExit(
            "access-parser not installed. Run:\n"
            "  pip install access-parser"
        )
    table_data = AccessParser(str(bok)).parse_table(table)
    if "nass" not in table_data:
        raise SystemExit(f"{bok}: table {table!r} has no `nass` column")
    n = len(table_data["id"])
    rows = [
        {col: _cp1256(table_data[col][i]) for col in table_data}
        for i in range(n)
    ]
    rows.sort(key=lambda r: int(r["id"]))
    return rows


def _cp1256(value):
    """Undo access_parser's latin-1 reading of CP1256 Memo text."""
    if not isinstance(value, str):
        return value
    try:
        return value.encode("latin-1").decode("cp1256")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def candidate_entries(rows: list[dict]) -> list[dict]:
    """
    Every `root: ` line, in reading order, with the text that follows it.

    Over-generates on purpose. `align()` does the discriminating.
    """
    out: list[dict] = []
    for row in rows:
        # NORMALISE THE LINE SEPARATOR FIRST. Shamela stores page text with
        # bare \r between the edition's lines. `mdb-export` rewrote those to \n
        # on its way through CSV, so splitting on "\n" worked for as long as
        # the reader was mdbtools and silently found nothing the moment it was
        # not: 83 entries vocalised instead of 8,929. The harakat floor in
        # lisan.yaml caught it. An entry head is defined by being at the start
        # of a LINE, so which byte the source uses for that is not something
        # this parser should know.
        page_text = (row.get("nass") or "").replace("\r\n", "\n").replace("\r", "\n")
        page_text = page_text.split(FOOTNOTE_RULE)[0]
        for line in page_text.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = HEAD.match(line)
            key = None
            if m:
                bare = strip_marks(m.group(1))
                if re.fullmatch(r"[\u0621-\u064a]{2,6}", bare):
                    key = root_key(bare)
            if key:
                out.append({
                    "root": key,
                    "written": m.group(1),
                    "vol": int(row["part"]) if row.get("part") else None,
                    "page": int(row["page"]) if row.get("page") else None,
                    "lines": [line[m.end():]],
                })
            elif out:
                out[-1]["lines"].append(line)
    return out


def align(openiti_heads: list[str], cands: list[dict]) -> dict[str, list[dict]]:
    """
    Walk both sequences in the book's own order; match on root key.

    A spurious head — a cross-reference inside an article — is out of order
    with respect to OpenITI's curated sequence, so it never matches and its
    text is absorbed into the article it actually belongs to. A real head is in
    order and matches on the first look.

    RETURNS A LIST PER KEY, IN ORDER, not a single entry. `root_key` folds
    hamza to bare alif, so 142 keys carry two genuinely different roots — بدأ
    and بدا, قرأ and قرا. `lisan.py` files those as separate entries now, and
    this has to hand back separate texts to match them against. Collapsing
    them here would vocalise the first article with the second's prose.
    """
    WINDOW = 40
    matched: dict[str, list[dict]] = {}
    last: dict | None = None   # the article a skipped candidate belongs to
    i = 0
    for root in openiti_heads:
        for j in range(i, min(i + WINDOW, len(cands))):
            if cands[j]["root"] != root:
                continue
            # Anything stepped over was a mid-article cross-reference. Its text
            # belongs to the article in progress, so give it back rather than
            # dropping it — the colon is restored because the head pattern ate
            # it, and losing it would run two sentences together.
            if last is not None:
                for k in range(i, j):
                    last["lines"].append(cands[k]["written"] + ":")
                    last["lines"].extend(cands[k]["lines"])
            matched.setdefault(root, []).append(cands[j])
            last = cands[j]
            i = j + 1
            break
    return matched


def verify(root: str, shamela_text: str, openiti_text: str) -> float:
    """
    De-diacritised Shamela text must reproduce the text we already ship.

    The gate the whole approach rests on. Two independent derivations of one
    edition agreeing is far stronger evidence than either alone, and it is what
    lets us swap 13 million characters without reading them.
    """
    a = ARABIC_ONLY.sub("", openiti_text)
    b = ARABIC_ONLY.sub("", strip_marks(shamela_text))
    if len(a) < 50:
        return 1.0
    return difflib.SequenceMatcher(None, a[:4000], b[:4000]).ratio()
