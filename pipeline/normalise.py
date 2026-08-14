"""
The normalisation that produces `search_key`. Phase 2.

This is THE join key between corpus tokens and the lexicon, so it is derived
from the workbook rather than from a description of it, and asserted to
reproduce all 22,464 `search_key` values exactly.

Derivation: the character inventories of `vocalized` and `search_key` differ by
exactly these counts, which fixes every rule with no room for guesswork —

    ا  13,009 -> 17,483   (+4,474 = أ 3,963 + إ 303 + آ 208)
    ي   7,526 ->  7,999   (  +473 = ى 473)
    ه   4,821 ->  6,763   (+1,942 = ة 1,942)
    ء     462 ->  1,069   (  +607 = ئ 439 + ؤ 168)

Note the hamza rule is NOT uniform, which the phrase "hamza forms unified"
obscures: alef-seated hamza folds to bare ALEF, while waw- and yeh-seated hamza
fold to bare HAMZA. Getting that backwards silently mis-joins ~600 forms.
"""

from __future__ import annotations

import re

# Harakat, tanwin, shadda, sukun, superscript alef, and tatweel.
DIACRITICS = str.maketrans(
    "",
    "",
    "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0653\u0654\u0655\u0670\u0640",
)


def dediac(text: str) -> str:
    """Strip diacritics ONLY — every letter stays itself. The exact tier for
    Lane headword matching: unlike normalise(), ة does not fold to ه, so
    هِجْرَة (emigration) cannot collide with هَجَرَهُ (he forsook him)."""
    return str(text).translate(DIACRITICS)

LETTERS = str.maketrans(
    {
        "\u0623": "\u0627",  # أ  alef with hamza above  -> alef
        "\u0625": "\u0627",  # إ  alef with hamza below  -> alef
        "\u0622": "\u0627",  # آ  alef with madda        -> alef
        "\u0649": "\u064a",  # ى  alef maksura           -> yeh
        "\u0629": "\u0647",  # ة  teh marbuta            -> heh
        "\u0626": "\u0621",  # ئ  yeh with hamza above   -> hamza
        "\u0624": "\u0621",  # ؤ  waw with hamza above   -> hamza
    }
)


def normalise(form: str) -> str:
    """Fold a vocalised surface form to its `search_key`."""
    return form.translate(DIACRITICS).translate(LETTERS)


# Root search needs a second, looser fold. The workbook writes hamza-initial
# roots with a bare hamza — ءرض, ءمر, ءتي — while a student types أرض, which
# normalise() turns into ارض. Without folding those together, searching for the
# root of a hamzated word silently returns nothing.
ROOT_EXTRA = str.maketrans({"\u0621": "\u0627"})  # ء -> ا


def root_key(root: str) -> str:
    """
    Canonical form of a ROOT, for lookup.

    Looser than `normalise` on purpose: recall matters more than precision when
    a reader is asking "what else comes from this root". Also drops the stray
    punctuation a few root values carry.
    """
    folded = normalise(root).translate(ROOT_EXTRA)
    return "".join(c for c in folded if "\u0621" <= c <= "\u064a")


# Root spellings differ between a modern analyser and Lane's 1863 conventions.
# These are the same root written two ways, not two roots:
#
#     ردد  /  رد     Lane collapses a geminate: two radicals, not three
#     مني  /  منى    Lane writes a final weak radical as alif maqsura
#     وهي  /  وهى    the same
#     ءمو  /  امو    Lane uses a bare alif where an analyser writes a hamza
#
# 4,408 entries carried a root Lane does not hold AS SPELLED. A classical shard
# was created for each, so the reader saw a root section with nothing in it —
# worse than the honest fallback to the root's first article, because it looked
# like Lane had nothing to say.
def root_variants(root: str) -> list[str]:
    """
    The root as written, then the spellings Lane might file it under.

    Ordered: the caller takes the first that exists, so an exact hit always
    wins and a variant is only ever a fallback.

    Three axes, combined. Each is the same root written two ways:

      hamza seat   ء أ إ آ ا    an analyser writes `أوي`, Lane writes `اوى`
      final weak   ي ى و        Lane prefers alif maqsura
      geminate     ردد -> رد    Lane collapses a doubled radical
    """
    # ئ and ؤ belong here too. A hamza sits on whichever letter carries it,
    # and that carrier is not part of the root: `ذئب` is Lane's `ذأب`. Their
    # absence cost exactly one entry, found by the invariant test when two
    # new corpora brought a word the others did not have.
    seats = "\u0621\u0623\u0625\u0622\u0627\u0626\u0624"   # ء أ إ آ ا ئ ؤ

    def seat_forms(r: str) -> list[str]:
        out = [r]
        for i, c in enumerate(r):
            if c in seats:
                for alt in seats:
                    if alt != c:
                        cand = r[:i] + alt + r[i + 1:]
                        if cand not in out:
                            out.append(cand)
        return out

    def weak_forms(r: str) -> list[str]:
        out = [r]
        for a in ("\u064a", "\u0649", "\u0648"):        # ي ى و
            if r.endswith(a):
                for b in ("\u064a", "\u0649", "\u0648"):
                    if b != a and r[:-1] + b not in out:
                        out.append(r[:-1] + b)
        return out

    def geminate_forms(r: str) -> list[str]:
        out = [r]
        if len(r) == 3 and r[1] == r[2]:
            out.append(r[:2])
        if len(r) == 3 and r[0] == r[1]:
            out.append(r[1:])
        return out

    out: list[str] = []
    for a in geminate_forms(root):
        for b in weak_forms(a):
            for c in seat_forms(b):
                if c not in out:
                    out.append(c)
    return out


_VOC_MARKS = "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0670"


def voc_key(text: str) -> str:
    """
    The TOP matching tier for Lane headwords: letters plus their own short
    vowels, order-normalised, with the final letter's case marks dropped
    (a headword carries a citation ending, a lemma carries its own). This is
    what tells هِجْرَةٌ (hijrah, emigration) from هُجْرَةٌ (hujrah) — twins
    at the diacritic-stripped tier, distinct words to a reader.
    """
    groups = re.findall(rf"([^\s{_VOC_MARKS}])([{_VOC_MARKS}]*)", str(text))
    out = []
    for i, (letter, marks) in enumerate(groups):
        if i == len(groups) - 1:
            marks = "".join(m for m in marks if m == "\u0651")  # keep shadda
        out.append(letter + "".join(sorted(marks)))
    return "".join(out)
