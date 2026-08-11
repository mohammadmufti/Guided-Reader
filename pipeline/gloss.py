"""
Parse the workbook's Buckwalter glosses into something a panel can render.

`gloss_msa` looks like `the + prayer;salat + [fem.sg.]`. It is a chain of
morphological slots joined by ` + `, where

  * `___` is an empty slot (always the proclitic position, 9,362 of them),
  * `;` separates alternative senses within a slot,
  * `[...]` carries morphological features, almost always on the final slot,
  * `<verb>` marks an enclitic that is a verb's subject pronoun.

Finding the STEM is the only hard part, and it is not positional. In
`the + prayer;salat + [fem.sg.]` the stem is slot 1, but in
`and + I + leave;quit` it is slot 2 — `I` is the imperfect subject prefix, not
the lexical content. So the stem is identified by elimination: the first slot
that is not an empty marker, not features-only, and not drawn from the closed
set of clitic glosses. That set is built from the data rather than guessed —
see CLITIC_GLOSSES, derived from what actually occupies the proclitic slot.

The parse runs at build time, not in the browser, so it can be checked against
all 21,028 glosses before anything ships.
"""

from __future__ import annotations

import re

RE_FEATURES = re.compile(r"\[([^\]]*)\]")
RE_POS_TAG = re.compile(r"<([^>]+)>")

# Segments that occupy the proclitic slot, plus the pronoun set that occupies
# the enclitic slot. Both are closed classes in this data.
CLITIC_GLOSSES = {
    "___",
    # conjunctions and prepositions
    "and", "and;so", "and/so", "so", "the", "by;with", "with/by", "with", "by",
    "for/to", "for", "to", "in", "from", "as", "then", "or", "not", "if",
    "a/one", "some/any",
    # subject and object pronouns, both slots
    "I", "we", "you", "he/it", "she/it", "it/they/she", "they", "they (people)",
    "they [fem.pl.]", "it/him", "its/his", "her/it", "its/their/her", "their",
    "my", "our", "your", "them", "us", "me", "him", "you [pl.]", "you [fem.]",
    "he/it it/him", "two",
}

PRONOUN_HINT = re.compile(
    r"^(I|we|you|he|she|it|they|them|us|me|him|her|its?|my|our|your|their)\b", re.I
)


class Slot:
    __slots__ = ("senses", "features", "pos", "raw", "empty")

    def __init__(self, raw: str) -> None:
        self.raw = raw
        text = raw.strip()
        self.pos = None
        m = RE_POS_TAG.search(text)
        if m:
            self.pos = m.group(1)
            text = RE_POS_TAG.sub(" ", text)
        self.features = [
            f.strip() for chunk in RE_FEATURES.findall(text) for f in chunk.split(".") if f.strip()
        ]
        text = RE_FEATURES.sub(" ", text)
        text = re.sub(r"\s+", " ", text).strip()
        self.empty = text == "___" or not text
        # Buckwalter writes a multi-word sense with underscores for the spaces:
        # `kneeling_down`, `make_a_pilgrimage`. They are spacing, not part of
        # the word, and a reader should not be shown the encoding. The workbook
        # was already written with spaces; the analyser's glosses are not, so
        # this only shows up on those.
        #
        # A sense that IS a single underscore is a placeholder and stays empty.
        # A `+` chain is CLITIC GLOSSES around the stem, not alternative
        # senses. CAMeL's `stemgloss` mostly gives the stem alone, but not
        # always: `بِسْمِ` comes back as `in;by_+_(the)_Name_of`, where
        # `in;by` glosses the attached bi- and only `(the) Name of` is the
        # word. Left unsplit, the whole chain became the sense list, and the
        # panel then showed a curated `in/by` beside a quick
        # `in, by + (the) Name of` — plainly the same meaning, and not
        # recognised as such.
        #
        # The stem is the LAST segment: Buckwalter writes proclitics first.
        if "+" in text:
            text = text.split("+")[-1].strip()
        self.senses = (
            [] if self.empty
            else [t for t in (s.strip().replace("_", " ").strip()
                              for s in text.split(";")) if t]
        )

    def is_clitic(self) -> bool:
        if self.empty:
            return True
        joined = ";".join(self.senses)
        if joined in CLITIC_GLOSSES:
            return True
        # A slot that is only a pronoun, with or without a <verb> tag, is a
        # clitic even if the exact string is not in the set.
        return len(self.senses) == 1 and bool(PRONOUN_HINT.match(self.senses[0])) and (
            self.pos is not None or len(self.senses[0].split()) <= 2
        )

    def as_dict(self) -> dict:
        return {
            "senses": self.senses,
            "features": self.features or None,
            "pos": self.pos,
        }


def parse_gloss(raw: str | None) -> dict | None:
    """
    -> {"senses": [...], "features": [...] | None,
        "before": [slot], "after": [slot], "stemIndex": int}

    `senses` is the stem's sense list — the thing a reader actually wants.
    `before` / `after` are the clitic chain around it. `features` are the
    morphological tags, hoisted out of whichever slot carried them.
    """
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None

    slots = [Slot(part) for part in text.split(" + ")]
    stem_index = next(
        (i for i, s in enumerate(slots) if not s.is_clitic()),
        None,
    )
    if stem_index is None:
        # Every slot looked like a clitic — the word IS a function word. Take
        # the longest non-empty slot rather than rendering nothing.
        candidates = [(len(";".join(s.senses)), i) for i, s in enumerate(slots) if not s.empty]
        if not candidates:
            return None
        stem_index = max(candidates)[1]

    stem = slots[stem_index]
    features = [f for s in slots for f in s.features]

    return {
        "senses": stem.senses,
        "features": features or None,
        "before": [s.as_dict() for s in slots[:stem_index] if not s.empty],
        "after": [s.as_dict() for s in slots[stem_index + 1 :] if not s.empty and s.senses],
        "stemPos": stem.pos,
    }


def comparable(senses: list[str]) -> set[str]:
    """
    A gloss reduced to what it MEANS, for comparing two of them.

    The two sources write the same meaning differently, and none of these
    differences is a difference in meaning:

      * the workbook packs alternatives into one string with a slash — `in/by`
        where the analyser lists `in`, `by`;
      * Buckwalter writes a multi-word sense with underscores, `kneeling_down`;
      * brackets carry an aside, `(the) Name of`;
      * a leading `to` or `be` is a citation habit, not a sense.

    THIS IS THE ONLY IMPLEMENTATION. It was written twice — once in Python for
    the comparison report, once in TypeScript to decide whether to show both
    glosses in the panel — and the two drifted, which is how duplicate glosses
    reappeared when two corpora were added. The panel now reads a flag this
    computes.
    """
    out: set[str] = set()
    for s in senses:
        s = re.sub(r"\([^)]*\)|\[[^\]]*\]", " ", str(s))
        for part in re.split(r"[/;,]", s.replace("_", " ")):
            t = re.sub(r"[^a-z ]", " ", part.lower())
            t = re.sub(r"\s+", " ", t).strip()
            t = re.sub(r"^(to|be|being) ", "", t)
            if t:
                out.add(t)
    return out


def says_the_same(a: dict | None, b: dict | None) -> bool:
    """Do two parsed glosses carry the same meaning? Both must exist."""
    if not a or not b:
        return False
    return comparable(a.get("senses") or []) == comparable(b.get("senses") or [])
