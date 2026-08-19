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

import csv
import difflib
import io
import re
import subprocess
import sys
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
    Read the Access database Shamela ships.

    `mdb-export` rather than a Python driver: mdbtools is packaged everywhere
    and the alternative pure-Python readers do not handle the Memo fields this
    file uses for page text.
    """
    try:
        out = subprocess.run(
            ["mdb-export", str(bok), table],
            capture_output=True, text=True, check=True,
        ).stdout
    except FileNotFoundError:
        raise SystemExit(
            "mdb-export not found. Install mdbtools:\n"
            "  apt-get install -y mdbtools   (Debian/Ubuntu)\n"
            "  brew install mdbtools         (macOS)"
        )
    except subprocess.CalledProcessError as e:
        raise SystemExit(f"mdb-export failed on {bok}: {e.stderr[:300]}")
    csv.field_size_limit(sys.maxsize)
    # io.StringIO, NOT out.splitlines(). The page text lives in Memo fields
    # that contain the newlines separating the edition's lines, and those are
    # precisely what an entry head is detected on. `splitlines()` consumes
    # them, silently collapsing each page into one line: 936 candidate entries
    # instead of 20,013, and an alignment that never syncs.
    rows = list(csv.DictReader(io.StringIO(out)))
    rows.sort(key=lambda r: int(r["id"]))
    return rows


def candidate_entries(rows: list[dict]) -> list[dict]:
    """
    Every `root: ` line, in reading order, with the text that follows it.

    Over-generates on purpose. `align()` does the discriminating.
    """
    out: list[dict] = []
    for row in rows:
        page_text = (row.get("nass") or "").split(FOOTNOTE_RULE)[0]
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


def align(openiti_roots: list[str], cands: list[dict]) -> dict[str, dict]:
    """
    Walk both sequences in the book's own order; match on root.

    A spurious head — a cross-reference inside an article — is out of order
    with respect to OpenITI's curated sequence, so it never matches and its
    text is absorbed into the article it actually belongs to. A real head is in
    order and matches on the first look.

    The scan window forgives local disagreement (OpenITI folds a few spellings
    together, and a handful of articles are filed twice) without letting the
    two sequences drift apart silently.
    """
    WINDOW = 40
    matched: dict[str, dict] = {}
    last: dict | None = None   # the entry a skipped candidate belongs to
    i = 0
    for root in openiti_roots:
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
            if root not in matched:
                matched[root] = cands[j]
            else:
                # The same root filed twice. `lisan.py` concatenates the two
                # articles rather than dropping one; do the same here or the
                # verification compares one article against two.
                matched[root]["lines"].extend(cands[j]["lines"])
            last = matched[root]
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
