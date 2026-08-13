#!/usr/bin/env python3
"""
Segment the OpenITI mARkdown file into `records.json`. Phase 1.

    python pipeline/segment.py                 # build + report
    python pipeline/segment.py --report-only   # rebuild but write nothing

Structure of the source, established empirically (see reports/phase1.md):

  * A metadata header terminated by `#META#Header#End#`.
  * Body lines are one of three kinds:
      `### | …`  structural line   (2,711 of them)
      `# …`      paragraph line    (7,686)
      `~~…`      continuation of the preceding line (8,432)
  * There is exactly ONE structural level. `### ||` never occurs, so the
    kitab/bab hierarchy is not encoded and has to be inferred: a heading
    beginning `كتاب` is a book, every other heading is a chapter of the book
    above it. This is validated against the workbook, not assumed.
  * A zawa'id addition is an UNNUMBERED body introduced by a `•` bullet and
    terminated by the note line `### | هذا الحديث من زوائد الضياء …`.
    88 bullets, 88 notes; the note is metadata on the record, not a record.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent
CACHE = ROOT / "cache"
REPORTS = ROOT / "reports"
OUT = ROOT / "build"

HEADER_END = "#META#Header#End#"

RE_META = re.compile(r"^#META#\s*([\w.]+)\s*::\s*(.*)$")


@dataclass
class Rules:
    """
    Every corpus-specific assumption, loaded from `corpora/{id}.yaml`.

    Phase 1 hard-coded these because there was one text. They are configuration
    now because OpenITI conventions differ between texts: the marker set, the
    opener grammar, the words that signal a book-level heading, and the editorial
    apparatus to strip are all properties of the edition, not of the format.
    """

    section: re.Pattern[str]
    paragraph: re.Pattern[str]
    continuation: re.Pattern[str]
    strip: list[tuple[str, re.Pattern[str]]]
    page: re.Pattern[str] | None
    page_alt: re.Pattern[str] | None
    opener: re.Pattern[str]
    bullet: re.Pattern[str] | None
    aside_marker: str | None
    heading_top_prefixes: tuple[str, ...]
    heading_prefixes: tuple[str, ...]
    front_prefixes: tuple[str, ...]
    aside_section_prefixes: tuple[str, ...]
    drop_section_prefixes: tuple[str, ...]
    unnumbered_body_is_aside: bool
    number_asides: bool
    section_levels: dict[str, str] | None
    opener_on: str
    numbering: str
    editorial_ref: re.Pattern[str] | None
    aside_ref: re.Pattern[str] | None
    layers: dict[str, str]
    emit_curated_index: bool

    @classmethod
    def from_config(cls, cfg: dict) -> "Rules":
        seg = cfg.get("segmentation", {})

        def rx(key: str, default: str | None = None) -> re.Pattern[str] | None:
            pat = seg.get(key, default)
            return re.compile(pat) if pat else None

        strip: list[tuple[str, re.Pattern[str]]] = []
        for item in seg.get("strip", []):
            strip.append((item["name"], re.compile(item["pattern"])))

        return cls(
            section=rx("section", r"^###\s*\|\s*(.*)$"),
            paragraph=rx("paragraph", r"^#\s(.*)$"),
            continuation=rx("continuation", r"^~~(.*)$"),
            strip=strip,
            page=rx("page_marker"),
            page_alt=rx("page_marker_alt"),
            opener=rx("opener", r"^(\d+)\s*-\s*(.*)$"),
            bullet=rx("aside_bullet"),
            aside_marker=seg.get("aside_marker"),
            heading_top_prefixes=tuple(seg.get("heading_top_prefixes", [])),
            heading_prefixes=tuple(seg.get("heading_prefixes", [])),
            front_prefixes=tuple(seg.get("front_prefixes", [])),
            aside_section_prefixes=tuple(seg.get("aside_section_prefixes", [])),
            drop_section_prefixes=tuple(seg.get("drop_section_prefixes", [])),
            unnumbered_body_is_aside=bool(
                seg.get("unnumbered_body_is_aside", False)),
            number_asides=bool(seg.get("number_asides", False)),
            section_levels=seg.get("section_levels"),
            opener_on=seg.get("opener_on", "section"),
            numbering=seg.get("numbering", "edition"),
            editorial_ref=rx("editorial_reference"),
            aside_ref=rx("aside_reference"),
            layers={
                "body": "matn", "aside": "zawaid", "top": "heading_kitab",
                "sub": "heading_bab", "front": "frontmatter",
                **(seg.get("layer_names") or {}),
            },
            emit_curated_index=bool(seg.get("curated_index_phantoms", False)),
        )


# A trailing footnote marker is not part of the sentence.
_TRAILING_REF = re.compile(r"(?:\s*\(\d+\))+\s*$")
_CLOSERS = ("»", ".", "؟", "!", "\u061f", ":")


def _sentence_closed(text: str) -> bool:
    """Did this record end a sentence, or is it waiting for the next line?"""
    t = _TRAILING_REF.sub("", str(text).rstrip()).rstrip()
    return t.endswith(_CLOSERS)


def count_tokens(text: str, rules: Rules) -> int:
    """
    Count tokens the way the workbook's pipeline did.

    Derived empirically, not documented anywhere: strip the editorial
    cross-reference, then count only tokens containing at least one Arabic
    letter. Bare dashes from the honorific `- رضي الله عنه -`, footnote digits,
    and stray punctuation are not tokens.

    This reproduces the workbook's own per-layer `layers` tallies to within
    46 tokens in 127,207 (0.036%). A naive whitespace split overshoots by 12.6%.
    """
    if rules.editorial_ref is not None:
        text = rules.editorial_ref.sub(" ", text)
    if rules.aside_ref is not None:
        text = rules.aside_ref.sub(" ", text)
    return sum(1 for tok in text.split() if RE_ARABIC.search(tok))


RE_ARABIC = re.compile(r"[\u0621-\u064a]")


def parse_header(text: str) -> dict[str, str]:
    meta: dict[str, str] = {}
    for line in text.split("\n"):
        m = RE_META.match(line)
        if m:
            key, val = m.group(1), m.group(2).strip()
            if val and val not in ("NODATA", "NOTGIVEN", "NOCODE"):
                meta[key] = val
    return meta


def join_continuations(lines: list[str], rules: Rules) -> list[str]:
    """Fold `~~` wrap-continuations into the logical line they continue."""
    out: list[str] = []
    for line in lines:
        m = rules.continuation.match(line)
        if m and out:
            out[-1] = f"{out[-1]} {m.group(1)}".strip()
        elif m:  # a continuation with nothing to continue — keep it, flag later
            out.append(m.group(1))
        else:
            out.append(line)
    return out


def strip_markers(text: str, rules: Rules) -> tuple[str, list[str]]:
    """
    Remove every structural marker from a line and return the printed page
    numbers it carried. Stripping order is deliberate: ms### markers occur
    *inside* both `<div …>` tags and `[ص: …]` brackets, so they go first.
    """
    pages: list[str] = []
    # Order matters and is configured, not assumed: manuscript markers occur
    # INSIDE both the div tags and the page brackets in al-Tajrid, so whichever
    # marker can nest must be stripped first. The yaml lists them in order.
    for name, pattern in rules.strip:
        if name == "page_volume" and rules.page_alt is not None:
            for vol, page in rules.page_alt.findall(text):
                if int(page) or int(vol):  # PageV00P000 is a null marker
                    pages.append(f"ص: {int(page)}")
        text = pattern.sub(" ", text)

    if rules.page is not None:
        for page in rules.page.findall(text):
            pages.append(f"ص: {int(page)}")
        text = rules.page.sub(" ", text)

    return re.sub(r"\s+", " ", text).strip(), pages


class Segmenter:
    def __init__(self, cfg: dict, rules: Rules) -> None:
        self.cfg = cfg
        self.rules = rules
        self.records: list[dict] = []
        self.current: dict | None = None
        self.pending_pages: list[str] = []
        self.kitab_idx = 0
        self.bab_idx = 0
        self.kitab: dict | None = None
        self.bab: dict | None = None
        self.warnings: list[str] = []
        # Layer of the most recent structural record, so a paragraph arriving
        # with no open record can be classified by what preceded it.
        self.last_structural: str | None = None
        # Depth of the open front-matter section, and whether we are inside
        # a part of the book whose records are ADDITIONS to it.
        self.front_depth: int | None = None
        self.in_aside_part = False
        # Inside a dropped block: a section whose title matches
        # `drop_section_prefixes` is discarded together with every paragraph
        # under it, until the next section line. Al-Adab al-Mufrad's chosen
        # edition needs this: it interleaves al-Albani's gradings as
        # `### | [قال الشيخ الألباني] :` followed by a paragraph — a modern
        # editor's matter, not the author's text, and left alone the fragment
        # path would REJOIN both into the hadith's matn, which is worse than
        # either showing or dropping them. Dropping is declared per corpus and
        # counted, so a config typo that never matches is visible in the run
        # report rather than silent.
        self.dropping = False
        self.dropped_sections = 0
        self.dropped_paragraphs = 0

    # -- record lifecycle ---------------------------------------------------
    def close(self) -> None:
        if self.current is not None:
            # Collapse whitespace, but a NEWLINE survives: it is never source
            # noise — feed() works line by line and every paragraph is
            # whitespace-flattened before it reaches a record — so the only
            # newline a record can hold is the deliberate separator the aside
            # merge writes between one hadith's several takhrij notes, which
            # the pane renders as a plain line break. Flattening it (as this
            # line did until it mattered) silently fused the notes back into
            # one run-on paragraph.
            t = re.sub(r"[^\S\n]+", " ", self.current["textRaw"])
            self.current["textRaw"] = re.sub(r" ?\n ?", "\n", t).strip()
            self.last_structural = self.current["layer"]
            self.records.append(self.current)
            self.current = None

    def open(self, *, rtype: str, layer: str, number: int | None, text: str) -> None:
        self.close()
        self.current = {
            "type": rtype,
            "layer": layer,
            "number": number,
            "kitab": dict(self.kitab) if self.kitab else None,
            "bab": dict(self.bab) if self.bab else None,
            "pages": list(self.pending_pages),
            "textRaw": text,
            "numbersCovered": [number] if number is not None else [],
            "zawaidNote": None,
            "crossRefs": [],
        }
        self.pending_pages = []

    def add_pages(self, pages: list[str]) -> None:
        target = self.current["pages"] if self.current is not None else self.pending_pages
        for p in pages:
            if p not in target:
                target.append(p)

    def add_text(self, text: str) -> None:
        if not text:
            return
        if self.current is None:
            # A paragraph arriving with no open record. What it is depends on
            # what closed last — this is where the two anomalies in the corpus
            # live, and defaulting everything to frontmatter mislabels them.
            if self.last_structural == self.rules.layers["top"]:
                # A chapter title carried as a plain paragraph rather than a
                # `### | ` line. Happens once (كيف كان بدء الوحي، under كتاب بدء الوحي).
                self.bab_idx += 1
                self.bab = {"index": self.bab_idx, "titleAr": text}
                self.open(rtype="bab", layer=self.rules.layers["sub"], number=None, text=text)
                self.close()
            elif (self.last_structural is None
                  or self.last_structural == self.rules.layers["front"]):
                # Nothing has opened yet, or the last thing that did was front
                # matter. Prose under a preface is still the preface: without
                # the second test, Nawawi's مقدمة produced two numbered body
                # records and the forty-two hadith ran 3-44.
                self.open(rtype="frontmatter", layer=self.rules.layers["front"], number=None, text=text)
            else:
                # Unnumbered narrative prose under a chapter — the sira material
                # in Kitab al-Manaqib. Body text, not front matter.
                layer = (self.rules.layers["aside"] if self.in_aside_part
                         else self.rules.layers["body"])
                self.open(rtype="hadith", layer=layer, number=None, text=text)
        else:
            self.current["textRaw"] += " " + text

    # -- the walk -----------------------------------------------------------
    def feed(self, logical_lines: list[str]) -> None:
        for lineno, line in enumerate(logical_lines, 1):
            if not line.strip():
                continue

            sec = self.rules.section.match(line)
            if sec:
                # A dropped block ends where the next section begins — whatever
                # that section is. Test the NEW title before clearing, so
                # consecutive dropped sections stay dropped.
                _title_for_drop = (sec.group(2) if (self.rules.section_levels
                                   and sec.lastindex and sec.lastindex >= 2)
                                   else sec.group(1))
                # Tested CLEANED and whitespace-collapsed, not raw: the
                # transcription plants ms markers inside the phrase itself
                # (`[قال ms002 الشيخ الألباني]`), and a raw-prefix test let
                # eleven of these through to the fragment path, which
                # rejoined the grading into the matn. (A first repair tried a
                # strip cleaner for the phrase instead — which this very test
                # then applied, emptying the title before the prefix could
                # match, so nothing dropped and the gradings fused anyway.
                # The corpus strip list is for markers INSIDE kept text; a
                # drop decision cleans structurally and compares.)
                if self.rules.drop_section_prefixes:
                    _t, _ = strip_markers(_title_for_drop, self.rules)
                    _t = re.sub(r"\s+", " ", _t).strip()
                    if _t.startswith(self.rules.drop_section_prefixes):
                        self.dropping = True
                        self.dropped_sections += 1
                        continue
                self.dropping = False
                # Two capture groups plus `section_levels` means the file states
                # its own hierarchy: group 1 is the level marker, group 2 the
                # title. One group means the level must be inferred lexically
                # from `heading_top_prefixes`, which is all al-Tajrid's single
                # `### |` level allows. Structural beats lexical wherever the
                # file offers it -- the Muwatta' writes `### | N - كتاب ...`,
                # whose title matches the numbered-opener rule and would
                # otherwise be read as a hadith.
                if self.rules.section_levels and sec.lastindex and sec.lastindex >= 2:
                    self.handle_section(
                        sec.group(2), lineno,
                        level=self.rules.section_levels.get(sec.group(1).strip()),
                        depth=len(sec.group(1).strip()),
                    )
                else:
                    self.handle_section(sec.group(1), lineno)
                continue

            para = self.rules.paragraph.match(line)
            if para:
                if self.dropping:
                    self.dropped_paragraphs += 1
                    continue
                self.handle_paragraph(para.group(1))
                continue

            # Anything else is bare text; treat as body but record it.
            clean, pages = strip_markers(line, self.rules)
            self.add_pages(pages)
            if clean:
                self.warnings.append(f"line {lineno}: unprefixed text {clean[:60]!r}")
                self.add_text(clean)

    def handle_section(self, payload: str, lineno: int, level: str | None = None,
                       depth: int = 1) -> None:
        clean, pages = strip_markers(payload, self.rules)

        # A page-marker line carries no other content — it is not a record.
        if not clean:
            self.add_pages(pages)
            return

        if self.rules.aside_marker and self.rules.aside_marker in clean:
            # Terminates the bulleted zawa'id body it annotates.
            if self.current is not None and self.current["layer"] == self.rules.layers["aside"]:
                self.current["zawaidNote"] = clean
            else:
                self.warnings.append(f"line {lineno}: zawa'id note with no preceding bullet body")
            self.close()
            self.add_pages(pages)
            return

        # A declared structural level is authoritative: this line is a
        # heading, whatever its text happens to look like.
        if level is not None:
            self.emit_heading(clean, level, depth)
            self.add_pages(pages)
            self.close()
            return

        # A "heading" that is neither an opener nor a heading is the source
        # being wrong, and Bulugh's is wrong 126 times: mid-sentence fragments
        # carry `### |` where the line before them ends unfinished —
        #
        #     ### | 2 -
        #     # وعن أبي سعيد الخدري ... قال: «إن
        #     ### | الماء طهور لا ينجسه شيء».
        #
        # Read as a heading, that split hadith 2 in half, orphaned its second
        # clause as a bab title, and left the takhrij note attached to nothing.
        # It belongs to the record still open, so it is appended to it.
        #
        # Declared by prefix, not guessed: a line is a heading when it starts
        # the way this book's headings start, and text otherwise. A corpus
        # that declares no prefixes keeps the old behaviour exactly.
        if (self.rules.heading_prefixes
                and self.current is not None
                and self.current.get("textRaw", "").strip()
                and not self.rules.opener.match(clean)
                and not clean.startswith(self.rules.heading_prefixes)):
            self.add_text(clean)
            self.add_pages(pages)
            return

        opener = self.rules.opener.match(clean)
        if opener:
            # A few openers carry more than one number: the source line
            # `### | 1201 - 1202 - ` is a single record covering both hadith.
            # There is no boundary in the text to split on, so the record keeps
            # every number it covers and all of them resolve to it. Dropping the
            # extras would look like a gap in the sequence that is not really there.
            numbers = [int(opener.group(1))]
            rest = opener.group(2)
            while True:
                nxt = self.rules.opener.match(rest)
                if not nxt:
                    break
                numbers.append(int(nxt.group(1)))
                rest = nxt.group(2)
            self.open(
                rtype="hadith", layer=self.rules.layers["body"], number=numbers[0], text=rest
            )
            assert self.current is not None
            self.current["numbersCovered"] = numbers
            self.add_pages(pages)
            return

        # Everything else is a heading. With one structural level in the file
        # the level has to be inferred lexically.
        is_top = bool(self.rules.heading_top_prefixes
                      and clean.startswith(self.rules.heading_top_prefixes))
        self.emit_heading(clean, "top" if is_top else "sub", depth)
        self.add_pages(pages)
        self.close()

    def emit_heading(self, clean: str, level: str | None, depth: int = 1) -> None:
        # Front matter is STICKY BY DEPTH. A section declared front matter keeps
        # everything nested under it as front matter, until a heading at the
        # same level or shallower closes it.
        #
        # Nawawi's ara2 edition has an appendix — باب الإشارات إلى ضبط الألفاظ
        # المشكلات, on vowelling difficult words — whose ten sub-headings are
        # `الحديث الأول`, `الحديث الثاني` and so on. They are references to
        # hadith, not hadith, and without this they became records 43-52 and
        # pushed Ibn Rajab's additions to 53-60.
        if self.front_depth is not None and depth > self.front_depth:
            self.open(rtype="frontmatter", layer=self.rules.layers["front"],
                      number=None, text=clean)
            return
        self.front_depth = None

        # A part of the book whose records are additions to it. Ibn Rajab's
        # ziyadat are eight hadith appended to Nawawi's forty-two, and they
        # should read as such — numbered and navigable like the rest, but
        # marked as another hand's.
        if self.rules.aside_section_prefixes and clean.startswith(
                self.rules.aside_section_prefixes):
            self.in_aside_part = True

        # A section that opens the book rather than belonging to its sequence.
        # Nawawi's preface and its `أما بعد` are sections like any other in the
        # file, and without this they take numbers 1 and 2 and push the forty
        # -two hadith to 3-44. Declared by prefix rather than by position: "the
        # first two sections" would be a guess about a file, while "the section
        # called مقدمة المؤلف" is a statement about a book.
        if self.rules.front_prefixes and clean.startswith(self.rules.front_prefixes):
            self.front_depth = depth
            self.open(rtype="frontmatter", layer=self.rules.layers["front"],
                      number=None, text=clean)
            return

        if level == "top":
            self.kitab_idx += 1
            self.bab_idx = 0
            self.kitab = {"index": self.kitab_idx, "titleAr": clean}
            self.bab = None
            self.open(rtype="kitab", layer=self.rules.layers["top"], number=None, text=clean)
        else:
            self.bab_idx += 1
            self.bab = {"index": self.bab_idx, "titleAr": clean}
            self.open(rtype="bab", layer=self.rules.layers["sub"], number=None, text=clean)

    def handle_paragraph(self, payload: str) -> None:
        clean, pages = strip_markers(payload, self.rules)
        self.add_pages(pages)
        if not clean:
            return

        # WHERE the numbered opener lives is part of the line grammar, not a
        # constant. al-Tajrid numbers on the section line (`### | 1 - ...`);
        # the Muwatta' numbers on a body line of its own (`# 1 - `) with the
        # text following on the next one. Assuming the former silently produced
        # one record per bab instead of one per hadith -- 703 records for a
        # text with about 1,600.
        if self.rules.opener_on in ("paragraph", "both"):
            opener = self.rules.opener.match(clean)
            if opener:
                numbers = [int(opener.group(1))]
                rest = opener.group(2)
                while True:
                    nxt = self.rules.opener.match(rest)
                    if not nxt:
                        break
                    numbers.append(int(nxt.group(1)))
                    rest = nxt.group(2)
                self.open(rtype="hadith", layer=self.rules.layers["body"],
                          number=numbers[0], text=rest)
                assert self.current is not None
                self.current["numbersCovered"] = numbers
                return

        # A further paragraph on a record that ALREADY HAS TEXT can be read
        # as a note on it — IF the corpus's trailing paragraphs really are an
        # apparatus. No corpus currently says so, and Bulugh is the reason
        # the flag defaults off: its trailing paragraphs (`وللبخاري: «…»`,
        # `أخرجه الثلاثة`, `وصححه أحمد`) were twice carved into an aside on
        # that theory, and twice reverted — they are ENTRY CONTENT, the
        # author's own text, inside the same single entry on the witness and
        # the same numbered hadith in the edition; carved out, they read as
        # footnotes attached to the wrong hadith. The machinery stays, fixed
        # (see the merge below), for a text whose trailing paragraphs are a
        # genuine apparatus.
        #
        # `textRaw` must be non-empty. A text that puts its number on a line of
        # its own leaves the record empty when its own body arrives, and
        # without this check that body is read as a note on nothing.
        # ONLY WHERE THE SENTENCE CLOSED. A note begins after the report ends;
        # a continuation resumes a sentence the previous line left open. The
        # source breaks lines mid-clause — hadith 5 ends `«إذا كان الماء قلتين`
        # and resumes `لم يحمل الخبث»` — so a rule that fires on every second
        # paragraph tore the matn in half and filed the rest as a footnote.
        #
        # 219 of Bulugh's 591 "notes" were continuations of this kind.
        #
        # ONE ASIDE PER HADITH, not one per paragraph. A hadith can carry
        # several takhrij paragraphs — hadith 2's `أخرجه الثلاثة` and
        # `وصححه أحمد` are two — and the first shipping of this feature opened
        # a new aside record for each, which the reader rendered as a stack of
        # separate aside sections under one hadith. They are one apparatus:
        # a further note on a record that is ALREADY the aside joins it,
        # separated by a newline the pane renders as a plain line break
        # (`whitespace-pre-line` on the aside only — the matn joins its
        # continuations with a space and never carries one).
        if (
            self.rules.unnumbered_body_is_aside
            and self.current is not None
            and self.current.get("textRaw", "").strip()
            and _sentence_closed(self.current["textRaw"])
            and self.current["layer"] in (
                self.rules.layers["body"], self.rules.layers["aside"])
        ):
            if self.current["layer"] == self.rules.layers["aside"]:
                self.current["textRaw"] += "\n" + clean
            else:
                self.open(rtype="hadith", layer=self.rules.layers["aside"],
                          number=None, text=clean)
            return

        bullet = self.rules.bullet.match(clean) if self.rules.bullet else None
        if bullet:
            # The record IS the added hadith; the note that follows is metadata on it.
            self.open(rtype="hadith", layer=self.rules.layers["aside"], number=None, text=bullet.group(1))
            return

        self.add_text(clean)

    # -- finish -------------------------------------------------------------
    def finalise(self) -> None:
        self.close()
        aside_layer = self.rules.layers.get("aside")
        for rec in self.records:
            refs: list[int] = []
            if self.rules.editorial_ref is not None:
                for m in self.rules.editorial_ref.finditer(rec["textRaw"]):
                    refs += [int(n) for n in re.findall(r"\d+", m.group(1))]
            # The ADDITIONS cite differently. al-Diya writes a bare `(4509)`
            # after the report and then comments on it, where al-Zabidi writes
            # `(بخاري: N)`. Same thing — the hadith in Bukhari — in a different
            # hand, and all 88 additions carry one.
            #
            # This was worth finding the hard way. Not seeing it, I built a
            # retrieval that guessed the number from the text instead: it
            # agreed with the editor on 1 of 76 and was systematically low,
            # landing on a neighbouring hadith in the same chapter whose
            # wording is near-identical. The number was in the file all along.
            if not refs and self.rules.aside_ref is not None and rec["layer"] == aside_layer:
                for m in self.rules.aside_ref.finditer(rec["textRaw"]):
                    refs += [int(n) for n in re.findall(r"\d+", m.group(1))]
            rec["crossRefs"] = refs

        for i, rec in enumerate(self.records, 1):
            rec["id"] = f"{rec['layer']}-{i:05d}"
            rec["seq"] = i
            rec["tokens"] = count_tokens(rec["textRaw"], self.rules)

        # ---- display numbering ------------------------------------------
        #
        # al-Tajrid numbers its hadith continuously, 1-2254, so `number` is
        # both what the edition prints and what a reader can be sent to.
        # The Muwatta' restarts at 1 in every kitab: 61 restarts and a maximum
        # of 255, which makes `number` alone ambiguous as an address -- there
        # are sixty-odd hadith 1.
        #
        # `numbering: continuous` assigns a running `displayNumber` over the
        # body layer in reading order and KEEPS the edition's own number in
        # `editionNumber`, so a citation can still be resolved against the
        # printed text. It is never invented where the edition already numbers
        # unambiguously; al-Tajrid declares nothing and gets `displayNumber ==
        # number`.
        body = self.rules.layers["body"]
        # Ibn Rajab's ziyadat are additions AND hadith: they are another hand's
        # work, and they are also numbers 43-50 of the book as it is read and
        # cited. al-Tajrid's zawa'id are the other case — unnumbered, and shown
        # beside the hadith they supplement — so which applies is declared.
        numbered = {body}
        if self.rules.number_asides:
            numbered.add(self.rules.layers["aside"])
        continuous = self.rules.numbering == "continuous"
        n = 0
        for rec in self.records:
            if rec["layer"] not in numbered:
                rec["displayNumber"] = None
                rec["editionNumber"] = None
                continue
            rec["editionNumber"] = rec["number"]
            if not continuous:
                rec["displayNumber"] = rec["number"]
                continue
            n += 1
            rec["displayNumber"] = n
            # `number` and `numbersCovered` ARE THE ADDRESS. Everything
            # downstream keys off them: `navigation.numberIndex`, the missing
            # -number report, audio matching, and the URL the reader lands on.
            #
            # Leaving the edition's own number here was a silent disaster on a
            # text that restarts numbering in every kitab. Sixty-one hadith call
            # themselves 1, so `numberIndex` kept only the last of each and
            # collapsed from 1,891 entries to 255 — every earlier hadith
            # unreachable by number, and `/muwatta/read/1` landing in kitab 61.
            #
            # The printed number is not lost; it is `editionNumber`, and with
            # its kitab it is what a citation should quote.
            rec["number"] = n
            rec["numbersCovered"] = [n]

        # Workbook index mapping.
        #
        # The workbook's `first_record` suffix is a GLOBAL record sequence in
        # reading order, not a per-type counter — which is why `zawaid-02638`
        # exceeds the 2,254 hadith count. Its pipeline emits one extra, EMPTY
        # record after every kitab heading not already followed by a bab
        # heading. We do not want 91 empty records in the reading order, so we
        # keep our own clean sequence and carry the workbook's index alongside.
        # That leaves `first_record` and `kwic` usable in Phases 2-3 without
        # polluting the data model.
        wi = 0
        for i, rec in enumerate(self.records):
            wi += 1
            rec["curatedIndex"] = wi
            if rec["layer"] == self.rules.layers["top"]:
                nxt = self.records[i + 1]["layer"] if i + 1 < len(self.records) else None
                if nxt != self.rules.layers["sub"]:
                    wi += 1  # phantom
        self.workbook_total = wi

        for i, rec in enumerate(self.records):
            rec["prev"] = self.records[i - 1]["id"] if i else None
            rec["next"] = self.records[i + 1]["id"] if i + 1 < len(self.records) else None


# Persian and Urdu codepoints for letters Arabic already has. They are the
# SAME letters -- a farsi kaf is a kaf -- but they sit outside `RE_WORD`'s
# \u0621-\u064a range, so a word containing one is not one word. `لَیْسَ` in
# Shah Wali Allah's Forty is written with U+06CC, and the tokeniser split it at
# that letter into two half-words, each separately hoverable.
#
# THE YEH IS NOT A SIMPLE SUBSTITUTION. Persian writes ی for what Arabic
# distinguishes as ي (dotted, a consonant or long i) and ى (alef maksura, a
# final long a). Folding every ی to ي changes words: `عَلَی` becomes `عَلَي`,
# which is the name Ali rather than the preposition on. Also affected here:
# السُّفْلَی, یَرَی, الْتَّقْوَی.
#
# The distinction is recoverable from the preceding vowel. A final ی after a
# kasra is a long i and takes the dotted form -- `فِیْ` is fi, `أُمَّتِیْ` is
# ummati. After a fatha, or after an unvowelled letter, it is alef maksura.
# Non-final ی is always the dotted form.
_HARAKAT = "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0670"
_KASRA = "\u0650"
_SIMPLE_VARIANTS = str.maketrans({
    "\u06a9": "\u0643",   # farsi kaf        -> kaf
    "\u06be": "\u0647",   # heh doachashmee  -> heh
    "\u06c1": "\u0647",   # heh goal         -> heh
    "\u0683": "\u062c",   # nyeh             -> jeem
})
_RE_PERSIAN_WORD = re.compile(r"[\u0600-\u06ff]+")


def _fold_word(word: str) -> str:
    out = list(word.translate(_SIMPLE_VARIANTS))
    if "\u06cc" not in out and "\u06d2" not in out:
        return "".join(out)
    last = max((i for i, c in enumerate(out) if c not in _HARAKAT), default=-1)
    for i, c in enumerate(out):
        if c not in ("\u06cc", "\u06d2"):
            continue
        if i != last:
            out[i] = "\u064a"
            continue
        # The vowel that matters belongs to the PRECEDING letter, so walk back
        # through this yeh's own marks (a sukun, typically) to reach it.
        j = i - 1
        vowel = None
        while j >= 0 and out[j] in _HARAKAT:
            if out[j] in "\u064e\u0650\u064f":
                vowel = out[j]
                break
            j -= 1
        out[i] = "\u064a" if vowel == _KASRA else "\u0649"
    return "".join(out)


def fold_letterforms(text: str) -> str:
    """Persian/Urdu letterforms -> their Arabic equivalents, word by word."""
    return _RE_PERSIAN_WORD.sub(lambda m: _fold_word(m.group(0)), text)


def read_source(source: Path) -> tuple[dict, str]:
    """
    (header metadata, body) for a corpus source, mARkdown or JSON.

    Most texts come from OpenITI as mARkdown. Some exist only as a hadith
    array — Shah Wali Allah's Forty is in no OpenITI repository at all, and the
    only machine-readable copy is the sunnah.com scrape. Rather than teach the
    segmenter a second grammar, that array is rendered INTO the grammar it
    already reads: one `### |` heading and one `#` body line per hadith. Every
    rule, layer and counter downstream then behaves identically, and the
    corpus config describes a mARkdown text because that is what it now is.
    """
    if source.suffix.lower() != ".json":
        raw = source.read_text(encoding="utf-8")
        if HEADER_END not in raw:
            raise SystemExit(f"{source.name}: no {HEADER_END} — not an OpenITI mARkdown file")
        header, body = raw.split(HEADER_END, 1)
        return parse_header(header), fold_letterforms(body)

    doc = json.loads(source.read_text(encoding="utf-8"))
    items = doc["hadiths"] if isinstance(doc, dict) else doc
    meta_src = (doc.get("metadata") or {}) if isinstance(doc, dict) else {}
    lines: list[str] = []
    for h in sorted(items, key=lambda x: int(x["idInBook"])):
        text = str(h.get("arabic") or "").strip()
        if not text:
            continue
        lines.append(f"### | الحديث {int(h['idInBook'])}")
        lines.append(f"# {text}")
    meta = {}
    ar = meta_src.get("arabic") or {}
    if ar.get("title"):
        meta["020.BookTITLE"] = ar["title"]
    return meta, fold_letterforms("\n".join(lines))


def _public_link(link: dict | None) -> dict | None:
    """The contract's ReferenceLink: label, labelAr, url — nothing else.

    The yaml blocks carry pipeline-only keys besides — `level` says which of
    OUR heading layers the chapter link keys on, `match` how the mapping is
    established, `layers` and `number_from_witness` steer the binder. None of
    them means anything to the client, and shipping the dict verbatim leaked
    `level: bab` into the Shama'il's index.json: a key the contract does not
    declare and no component reads. The payload states the contract, exactly.
    """
    if not link:
        return None
    return {k: link.get(k) for k in ("label", "labelAr", "url")}


def build(cfg: dict, source: Path, rules: Rules) -> tuple[dict, Segmenter]:
    meta, body = read_source(source)

    seg = Segmenter(cfg, rules)
    seg.feed(join_continuations(body.split("\n"), rules))
    seg.finalise()

    import hashlib

    disp = cfg["display"]
    corpus = {
        "id": cfg["id"],
        "titleAr": meta.get("020.BookTITLE", disp["titleAr"]),
        "titleEn": disp["titleEn"],
        "author": disp["author"],
        "authorDied": disp.get("authorDied"),
        "sourceUri": cfg["sources"]["text"]["uri"],
        "sourceRetrieved": json.loads(
            (CACHE / f"manifest-{cfg['id']}.json").read_text(encoding="utf-8")
        )["sources"]["text"]["retrieved"],
        "sourceSha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "edition": disp.get("edition"),
        "referenceLink": _public_link((cfg.get("segmentation") or {}).get("reference_link")),
        # Per-CHAPTER external reference. sunnah.com publishes the Muwatta'
        # as one page per book with no per-hadith anchor, so the link that
        # actually resolves is to the kitab.
        "chapterLink": _public_link((cfg.get("segmentation") or {}).get("chapter_link")),
        "recordLink": _public_link((cfg.get("segmentation") or {}).get("record_link")),
        # Which layer holds additions, and what to say about them. Both were
        # a hardcoded Arabic sentence in Reader.tsx naming al-Diya' al-Daghistani.
        "asideLayer": (cfg.get("segmentation") or {}).get("layer_names", {}).get("aside"),
        "asideNote": (cfg.get("display") or {}).get("asideNote"),
        # The "about this book" popup, verbatim from the corpus file — the
        # component holds no book knowledge; a second text writes its own.
        "about": cfg.get("about"),
    }

    ordered = [r["id"] for r in seg.records]
    number_index = {
        str(n): r["id"] for r in seg.records for n in r["numbersCovered"]
    }
    public_keys = (
        "id", "number", "displayNumber", "editionNumber", "type", "layer", "kitab",
        "bab", "pages", "textRaw", "prev", "next",
        "seq", "curatedIndex", "tokens", "numbersCovered", "zawaidNote", "crossRefs",
    )
    doc = {
        "corpus": corpus,
        "records": [{k: r[k] for k in public_keys} for r in seg.records],
        "navigation": {"orderedIds": ordered, "numberIndex": number_index},
    }
    return doc, seg


# ---------------------------------------------------------------------------
# Gate assertions
# ---------------------------------------------------------------------------
def residual_patterns(rules: Rules) -> dict[str, re.Pattern[str]]:
    """Anything the rules said to strip must not survive into a record."""
    pats = {name: pattern for name, pattern in rules.strip}
    pats["section marker"] = re.compile(r"###")
    pats["continuation"] = re.compile(r"~~")
    if rules.page is not None:
        pats["page bracket"] = rules.page
    return pats


def check_residuals(doc: dict, rules: Rules) -> dict[str, list[str]]:
    RESIDUALS = residual_patterns(rules)
    hits: dict[str, list[str]] = {k: [] for k in RESIDUALS}
    for rec in doc["records"]:
        blob = rec["textRaw"] + " " + (rec["zawaidNote"] or "")
        for kitab_or_bab in ("kitab", "bab"):
            node = rec.get(kitab_or_bab)
            if node:
                blob += " " + node["titleAr"]
        for name, pat in RESIDUALS.items():
            if pat.search(blob):
                hits[name].append(rec["id"])
    return hits


def write_report(doc: dict, seg: "Segmenter", stats: dict, corpus: str) -> Path:
    """Emit reports/phase1.md — the human-readable gate artifact."""
    recs = doc["records"]
    by_id = {r["id"]: r for r in recs}
    L: list[str] = []
    a = L.append

    a("# Phase 1 — corpus segmentation report\n")
    a(f"Source: `{doc['corpus']['sourceUri'].rsplit('/', 1)[-1]}`  ")
    a(f"sha256 `{doc['corpus']['sourceSha256'][:16]}…`  ")
    a(f"retrieved {doc['corpus']['sourceRetrieved']}\n")

    a("## Record counts\n")
    a("| layer | records | tokens | workbook | delta |")
    a("|---|--:|--:|--:|--:|")
    for layer, n in stats["by_layer"].most_common():
        wb = stats["wb_layers"].get(layer, 0)
        a(f"| `{layer}` | {n:,} | {stats['tok_layer'][layer]:,} | {wb:,} | "
          f"{stats['tok_layer'][layer]-wb:+,} |")
    a(f"| **total** | **{len(recs):,}** | **{stats['tokens']:,}** | **127,207** | "
      f"**{stats['tokens']-127207:+,}** ({100*(stats['tokens']-127207)/127207:+.3f}%) |\n")

    a("## Hadith numbering\n")
    a(f"- {stats['n_numbered']:,} numbered hadith, running 1–{stats['max_num']}.")
    a(f"- Missing numbers ({len(stats['missing'])}): "
      f"{', '.join(str(n) for n in stats['missing']) or 'none'}.")
    a(f"- Merged openers: {len(stats['merged'])} — "
      f"{', '.join('+'.join(map(str, r['numbersCovered'])) for r in stats['merged']) or 'none'}. "
      f"The source puts these on one line; the record covers both numbers and both resolve to it.")
    a(f"- Unnumbered matn records: {stats['unnumbered']} "
      f"(narrative prose under a chapter heading, no opener in the source).")
    a(f"- Zawa'id additions: {stats['n_zawaid']}, each carrying the al-Daghistani note.\n")

    a("## Structure\n")
    a(f"- Kitab headings: {stats['by_layer']['heading_kitab']}")
    a(f"- Bab headings: {stats['by_layer']['heading_bab']}")
    a(f"- Bukhari cross-references: {stats['n_bukh']:,} records carry `(بخاري: N)`, "
      f"naming {stats['n_bukh_distinct']:,} distinct Bukhari hadith.\n")

    a("## Residual-marker assertion\n")
    a("Every record's `textRaw`, `zawaidNote`, and kitab/bab titles were scanned for "
      "`PageV`, `ms###`, `[ص:`, `###`, `<div`, and `~~`.\n")
    bad = {k: v for k, v in stats["residuals"].items() if v}
    a(f"**Result: {'PASS — no residuals' if not bad else f'FAIL — {bad}'}**\n")

    a("## Three records in full\n")
    for label, rid in stats["samples"]:
        r = by_id[rid]
        num = f"number {r['number']}, " if r["number"] is not None else ""
        a(f"### {label} — `{r['id']}` ({num}{r['tokens']} tokens)\n")
        if r["kitab"]:
            a(f"*Kitab {r['kitab']['index']}: {r['kitab']['titleAr']}*  ")
        if r["bab"]:
            a(f"*Bab {r['bab']['index']}: {r['bab']['titleAr']}*  ")
        a(f"*Pages: {', '.join(r['pages']) or '—'}*  ")
        a(f"*Bukhari: {', '.join(map(str, r['crossRefs'])) or '—'}*\n")
        a(f"> {r['textRaw']}\n")
        if r["zawaidNote"]:
            a(f"**Zawa'id note:** {r['zawaidNote']}\n")

    REPORTS.mkdir(parents=True, exist_ok=True)
    path = REPORTS / (f"phase1-{corpus}.md" if corpus != "tajrid" else "phase1.md")
    path.write_text("\n".join(L), encoding="utf-8")
    return path


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--corpus", default="tajrid")
    ap.add_argument("--report-only", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load((ROOT / "corpora" / f"{args.corpus}.yaml").read_text(encoding="utf-8"))
    source = CACHE / cfg["id"] / cfg["sources"]["text"]["filename"]
    rules = Rules.from_config(cfg)
    doc, seg = build(cfg, source, rules)

    recs = doc["records"]
    by_layer = Counter(r["layer"] for r in recs)
    tok_layer = Counter()
    for r in recs:
        tok_layer[r["layer"]] += r["tokens"]
    numbers = sorted(n for r in recs for n in r["numbersCovered"]) or [0]
    merged = [r for r in recs if len(r["numbersCovered"]) > 1]
    missing = sorted(set(range(1, max(numbers) + 1)) - set(numbers))
    tokens = sum(tok_layer.values())
    raw_tokens = sum(len(r["textRaw"].split()) for r in recs)

    # The workbook's own per-layer tallies, recovered from the `layers` column.
    expected = (cfg.get("expected") or {}).get("layer_tokens") or {}
    WB_LAYERS = {k: int(v) for k, v in expected.items()}
    WB_TOTAL = sum(WB_LAYERS.values())

    print(f"records            {len(recs):>8,}   (workbook sequence spans {seg.workbook_total:,})")
    print(f"{'layer':<19}{'records':>9}{'tokens':>10}{'workbook':>10}{'delta':>8}")
    for layer, n in by_layer.most_common():
        wb = WB_LAYERS.get(layer, 0)
        print(f"  {layer:<17}{n:>9,}{tok_layer[layer]:>10,}{wb:>10,}{tok_layer[layer]-wb:>+8,}")
    if WB_TOTAL:
        print(f"  {'TOTAL':<17}{len(recs):>9,}{tokens:>10,}{WB_TOTAL:>10,}"
              f"{tokens-WB_TOTAL:>+8,}   ({100*(tokens-WB_TOTAL)/WB_TOTAL:+.3f}%)")
        print(f"raw whitespace split {raw_tokens:,} — "
              f"{100*(raw_tokens-WB_TOTAL)/WB_TOTAL:+.2f}% (for contrast)")
    else:
        print(f"  {'TOTAL':<17}{len(recs):>9,}{tokens:>10,}"
              f"{'—':>10}{'—':>8}   (no expected tallies configured)")
    print(f"hadith numbers     {min(numbers)}–{max(numbers)}, {len(missing)} missing: {missing}")
    print(f"merged openers     {len(merged)}: "
          f"{[r['numbersCovered'] for r in merged]}")
    print(f"unnumbered matn    {sum(1 for r in recs if r['layer']=='matn' and r['number'] is None)}")
    print(f"zawa'id notes      {sum(1 for r in recs if r['zawaidNote']):>8,}")
    print(f"Bukhari refs       {sum(1 for r in recs if r['crossRefs']):>8,} records, "
          f"{len({n for r in recs for n in r['crossRefs']}):,} distinct Bukhari numbers")

    hits = check_residuals(doc, rules)
    bad = {k: v for k, v in hits.items() if v}
    print(f"\nresidual markers   {'NONE' if not bad else bad}")
    if seg.rules.drop_section_prefixes:
        print(f"dropped blocks     {seg.dropped_sections} sections, "
              f"{seg.dropped_paragraphs} paragraphs "
              f"(declared drop_section_prefixes; zero here means the config "
              f"matched nothing)")
    if seg.warnings:
        print(f"warnings ({len(seg.warnings)}):")
        for w in seg.warnings[:10]:
            print("  ", w)

    # Gate requires three records printed in full: one short, one long, one
    # carrying a zawa'id note.
    # A corpus need not have numbered records at all — a geographical dictionary
    # has none — so fall back to the body layer, and to every record after that.
    # The first version of this crashed with `min() arg is an empty sequence` on
    # the second corpus, which is precisely the kind of thing a generalisation
    # claim is worth nothing without testing.
    body_layer = seg.rules.layers["body"]
    pool = [r for r in recs if r["layer"] == body_layer and r["number"] is not None]
    if not pool:
        pool = [r for r in recs if r["layer"] == body_layer] or recs
    shortest = min(pool, key=lambda r: r["tokens"])
    longest = max(pool, key=lambda r: r["tokens"])
    with_note = next((r for r in recs if r["zawaidNote"]), None)
    stats = {
        "by_layer": by_layer, "tok_layer": tok_layer, "tokens": tokens,
        "wb_layers": WB_LAYERS, "missing": missing, "max_num": max(numbers),
        "n_numbered": len(numbers), "residuals": hits, "merged": merged,
        "unnumbered": sum(1 for r in recs if r["layer"] == "matn" and r["number"] is None),
        "n_zawaid": sum(1 for r in recs if r["zawaidNote"]),
        "n_bukh": sum(1 for r in recs if r["crossRefs"]),
        "n_bukh_distinct": len({n for r in recs for n in r["crossRefs"]}),
        "samples": [("Shortest record", shortest["id"]), ("Longest record", longest["id"])]
        + ([("Aside / addition", with_note["id"])] if with_note else []),
    }

    if not args.report_only:
        out_dir = OUT / args.corpus
        out_dir.mkdir(parents=True, exist_ok=True)
        path = out_dir / "records.json"
        path.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"\nwrote {path.relative_to(ROOT.parent)}  ({path.stat().st_size/1e6:.2f} MB)")
    rp = write_report(doc, seg, stats, args.corpus)
    print(f"wrote {rp.relative_to(ROOT.parent)}")

    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
