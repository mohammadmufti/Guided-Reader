"""
Restore a printed edition's harakāt onto records segmented from a stripped text.

THE PROBLEM THIS SOLVES. OpenITI normalises diacritics away. Every version of
every book checked so far is affected — all four of Lisān al-ʿArab, all six of
Riyāḍ al-Ṣāliḥīn, all four of al-Nihāya, each with exactly zero combining marks
of any Unicode category. Our fetch is not at fault; the files match upstream's
checksums byte for byte. Shamela's own distribution of the SAME editions keeps
the marks:

                        Arabic letters   combining marks   ratio
    Riyāḍ .bok                 580,449           249,395   0.430
    Riyāḍ via OpenITI          491,003                 0   0.000

WHY THIS IS A SWAP AND NOT A WITNESS. `bind.py` can already take a vocalised
edition as a witness and align against it, which is how al-Tajrīd reaches Tier
2. But a witness is a DIFFERENT edition of the same book: alignment is
approximate, and a reading is attributed by inference. Here the .bok is the
very edition the stripped text was derived from, so the consonantal skeletons
are identical — 99.95% of Riyāḍ's records appear VERBATIM in it. That makes the
mapping positional and lossless, and puts the corpus on Tier 0, "the source is
vowelled", rather than Tier 2, "a witness suggests this reading".

DIACRITISATION.md §4 forbids INVENTING vocalisation. Nothing here is invented:
these are the editor's marks, as printed, restored to the position they were
printed in.

HOW IT WORKS, AND WHY IT DOES NOT SEGMENT THE .bok. Three ways of splitting the
.bok into hadith were tried and all failed:

  * keying on the `Hno` column — a row's number marks where a hadith STARTS,
    and long hadith continue onto unnumbered rows (median similarity 0.940);
  * splitting on `N - ` openers — bab headings number themselves with
    Arabic-Indic digits, so they do not match and accumulation runs past the
    end of the hadith;
  * carrying unnumbered rows forward — over-runs the other way, absorbing
    heading pages into the preceding hadith.

None of it is necessary. `segment.py` has ALREADY decided where each record
begins and ends. So the .bok is flattened into one stream, each record's own
consonantal skeleton is located in it, and the vocalised span is taken back.
The book never needs segmenting twice.

THE GATE. Strip the marks from what is taken and it must reproduce, character
for character, the text that was already there. A record that fails keeps its
bare text. On Riyāḍ that is 2,082 of 2,083 records restored and zero failures.
"""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path

# U+0640 TATWEEL sits INSIDE the 0621–064A letter range and is decoration, not
# a letter: the .bok writes بـ and هـ where the OpenITI text does not. Counting
# it as a consonant cost five of six failures on the first run.
TATWEEL = "\u0640"

# Shamela separates the editors' footnotes from the page body with a rule. They
# are real content, and the OpenITI text does not carry them, so including them
# here would insert text the reader's record never had.
FOOTNOTE_RULES = ("¬__________", "__________")

# Editorial furniture inside the page body: footnote anchors `(¬1)`, printed
# page markers `-[108]-`, and the stray `¬` that introduces both.
FURNITURE = [re.compile(p) for p in (r"\(¬\d+\)", r"-\s*\[\s*\d+\s*\]\s*-", r"¬")]


def is_letter(ch: str) -> bool:
    return "\u0621" <= ch <= "\u064a" and ch != TATWEEL


def rasm(text: str) -> str:
    """The consonantal skeleton: letters only, no marks, no tatweel."""
    return "".join(c for c in text if is_letter(c))


def strip_marks(text: str) -> str:
    """Every combining mark, not a hand-listed set of harakāt."""
    return "".join(c for c in text if not unicodedata.category(c).startswith("M"))


def read_bok(path: Path, table: str) -> list[dict]:
    """
    Read the Access database Shamela ships, in page order.

    Pure Python on purpose. An earlier version shelled out to `mdb-export`,
    which meant `apt-get install mdbtools` on every cold CI runner; that step
    hung for six hours and was killed by the job timeout.
    """
    try:
        from access_parser import AccessParser
    except ImportError:
        raise SystemExit("access-parser not installed. Run: pip install access-parser")
    data = AccessParser(str(path)).parse_table(table)
    if "nass" not in data:
        raise SystemExit(f"{path}: table {table!r} has no `nass` column")
    n = len(data["id"])
    rows = [{col: _cp1256(data[col][i]) for col in data} for i in range(n)]
    rows.sort(key=lambda r: int(r["id"]))
    return rows


def _cp1256(value):
    """
    Undo access_parser's latin-1 reading of CP1256 Memo text.

    These are old Shamela databases in the Windows Arabic codepage rather than
    UCS-2, so the text arrives as `Ü[áÓÇä ÇáÚÑÈ]Ü` for `ـ[لسان العرب]ـ`.
    """
    if not isinstance(value, str):
        return value
    try:
        return value.encode("latin-1").decode("cp1256")
    except (UnicodeEncodeError, UnicodeDecodeError):
        return value


def build_stream(rows: list[dict]) -> tuple[str, str, list[int]]:
    """
    Flatten the book into one vocalised stream, plus its skeleton and an index.

    `index[i]` is the offset in `vocalised` of the i-th letter of `skeleton`,
    which is what lets a span located in the skeleton be lifted back out with
    its marks attached.
    """
    parts = []
    for row in rows:
        text = str(row.get("nass") or "")
        for rule in FOOTNOTE_RULES:
            text = text.split(rule)[0]
        text = re.sub(r"[\r\n]", " ", text)
        for pattern in FURNITURE:
            text = pattern.sub(" ", text)
        parts.append(text)
    vocalised = " ".join(parts)
    letters, index = [], []
    for i, ch in enumerate(vocalised):
        if is_letter(ch):
            letters.append(ch)
            index.append(i)
    return vocalised, "".join(letters), index


def restore(records: list[dict], rows: list[dict], field: str = "textRaw") -> dict:
    """
    Rewrite each record's text with the edition's vocalised original.

    Records are searched IN ORDER, each from a little before where the last one
    ended. The book runs in one direction and so do we; a global search would
    let a short record match an earlier repetition of the same wording, which
    in a hadith collection is a real hazard rather than a theoretical one.
    """
    vocalised, skeleton, index = build_stream(rows)
    stats = {"restored": 0, "unmatched": 0, "verify_failed": 0, "skipped": 0}
    cursor = 0
    for record in records:
        original = record.get(field) or ""
        want = rasm(original)
        if len(want) < 20:
            # Too short to locate safely: a handful of letters will match
            # somewhere regardless, and being wrong here is worse than being
            # bare.
            stats["skipped"] += 1
            continue
        at = skeleton.find(want, max(0, cursor - 2000))
        if at < 0:
            at = skeleton.find(want)
        if at < 0:
            stats["unmatched"] += 1
            continue
        span = vocalised[index[at]: index[at + len(want) - 1] + 1]
        span = re.sub(r"\s+", " ", span).strip()
        # THE GATE. Strip the marks and it must reproduce what was already
        # there. Anything else means the span is not this record's text, and a
        # doubtful substitute is worse than a bare one.
        if rasm(strip_marks(span)) != want:
            stats["verify_failed"] += 1
            continue
        record[field] = span
        stats["restored"] += 1
        cursor = at + len(want)
    marks = sum(
        1 for r in records for c in (r.get(field) or "")
        if unicodedata.category(c).startswith("M")
    )
    letters = sum(1 for r in records for c in (r.get(field) or "") if is_letter(c))
    stats["ratio"] = marks / letters if letters else 0.0
    return stats
