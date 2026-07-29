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

# Harakat, tanwin, shadda, sukun, superscript alef, and tatweel.
DIACRITICS = str.maketrans(
    "",
    "",
    "\u064b\u064c\u064d\u064e\u064f\u0650\u0651\u0652\u0653\u0654\u0655\u0670\u0640",
)

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
