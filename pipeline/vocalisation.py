"""
What vowelling does the SOURCE already carry? Phase 2.

Every corpus configured so far is bare, and a 179-text sample of OpenITI turned
up no vocalised text at all (95% CI upper bound ~1.7%). But the vocalised
Bukhari and Muwatta' witnesses this pipeline already fetches are 98.7% vowelled,
and any corpus taken from Shamela directly, from Tanzil, or from a hadith
dataset rather than from OpenITI will arrive with marks on it. The binding
precedence had no slot for that: the surface resolved witness -> lexicon -> raw,
so a source haraka was reachable only for a token that bound to nothing at all.

The interesting case is not "vowelled" or "bare". It is PARTIAL. A Shamela text
typically vowels Qur'anic quotations, lines of verse, and the odd word an
editor thought ambiguous, and leaves the surrounding prose alone. Worse, a
partially-marked token is common: `اللّه` carries a shadda and no vowels;
`مُحَمَّد` carries three marks but no case ending. Treating either as "vowelled"
throws away the witness for no gain, and treating them as "bare" throws away a
real constraint.

So three classes, decided per TOKEN and never per corpus:

    NONE     no marks at all -> the existing pipeline, unchanged
    PARTIAL  marks, but no final short vowel -> CONSTRAINS the candidates
    FULL     carries a final short vowel -> Tier 0, outranks every inference

The final short vowel is the dividing line because it is what actually carries
i'rab, which is what the witness and the lexicon are being consulted for in the
first place. A word marked everywhere except its ending has not answered the
question being asked.
"""

from __future__ import annotations

NONE, PARTIAL, FULL = "none", "partial", "full"

# Short vowels and tanwin: the case/mood markers.
HARAKAT = frozenset("\u064e\u064f\u0650\u064b\u064c\u064d")
# Everything else that is a mark rather than a letter: shadda, sukun, the
# hamza-seat marks, superscript alef. Present in a "vowelled" text but not
# themselves evidence of i'rab.
OTHER_MARKS = frozenset("\u0651\u0652\u0653\u0654\u0655\u0670")
MARKS = HARAKAT | OTHER_MARKS
TATWEEL = "\u0640"


def split_marks(form: str) -> tuple[str, dict[int, str]]:
    """
    Separate a form into its letter skeleton and the marks hanging off it.

    Returns (letters, {letter_index: marks_following_that_letter}). Tatweel is
    dropped: it is a shaping artefact, and a source that uses it must still
    compare equal to a lexicon entry that does not.
    """
    letters: list[str] = []
    marks: dict[int, str] = {}
    for ch in form:
        if ch == TATWEEL:
            continue
        if ch in MARKS:
            if letters:
                marks[len(letters) - 1] = marks.get(len(letters) - 1, "") + ch
        else:
            letters.append(ch)
    return "".join(letters), marks


def classify(raw: str) -> str:
    """NONE, PARTIAL or FULL for one source token."""
    letters, marks = split_marks(raw)
    if not marks:
        return NONE
    return FULL if final_haraka(letters, marks) else PARTIAL


def final_haraka(letters: str, marks: dict[int, str]) -> str | None:
    """
    The short vowel on the LAST LETTER, or None.

    Deliberately the last letter and not the last MARKED letter. `مُحَمَّد` is
    marked throughout and bare on its final dal; reading the fatha on the
    preceding mim as the ending would classify a word that has said nothing
    about its own i'rab as though it had settled the question. Caught by
    test_marks_without_a_final_vowel_are_partial, which is why it is stated
    twice.
    """
    if not letters:
        return None
    for ch in reversed(marks.get(len(letters) - 1, "")):
        if ch in HARAKAT:
            return ch
    return None


def is_consistent(raw: str, candidate: str) -> bool:
    """
    Could `candidate` be a fuller vowelling of `raw`?

    True when the letter skeletons agree and every mark the SOURCE supplies is
    also present in the candidate at the same letter. The candidate may add
    marks the source omitted -- that is the whole point -- but it may not
    contradict one. `مُحَمَّد` is consistent with `مُحَمَّدٌ` and with `مُحَمَّدٍ`,
    and not with `مَحْمُود`.

    This is what makes PARTIAL useful rather than merely awkward: a partially
    marked token cannot pick its own reading, but it can rule most of them out.
    """
    r_letters, r_marks = split_marks(raw)
    c_letters, c_marks = split_marks(candidate)
    if r_letters != c_letters:
        return False
    for i, ms in r_marks.items():
        got = c_marks.get(i, "")
        if any(m not in got for m in ms):
            return False
    return True


def agrees(raw: str, candidate: str) -> bool:
    """
    Does the candidate reproduce a FULLY vowelled source token exactly?

    Compared through split_marks rather than by string equality so that mark
    ORDER (shadda-then-fatha versus fatha-then-shadda, both of which occur in
    real files) and stray tatweel do not read as disagreement. A difference
    here is a real one, and worth counting: it means the witness edition and
    the source edition disagree about the word, which is a fact about the
    editions rather than a bug in the pipeline.
    """
    r_letters, r_marks = split_marks(raw)
    c_letters, c_marks = split_marks(candidate)
    if r_letters != c_letters:
        return False
    return {i: set(m) for i, m in r_marks.items()} == {i: set(m) for i, m in c_marks.items()}
