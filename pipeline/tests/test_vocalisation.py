"""
Source vocalisation: classification, consistency, agreement. Phase 2.

Every corpus configured today is bare, so none of this fires in production yet.
That is exactly why it needs tests: the path would otherwise ship unexercised
and be discovered wrong by the first vocalised text.
"""

import pytest

from vocalisation import (
    FULL, NONE, PARTIAL, agrees, classify, is_consistent, split_marks,
)


# ---------------------------------------------------------------- classify --

def test_bare_token_is_none():
    assert classify("محمد") == NONE
    assert classify("الاعمال") == NONE


def test_fully_vowelled_token_is_full():
    assert classify("مُحَمَّدٌ") == FULL      # dammatan ending
    assert classify("الْأَعْمَالُ") == FULL
    assert classify("بِسْمِ") == FULL          # kasra ending


def test_marks_without_a_final_vowel_are_partial():
    """The case that a per-corpus flag cannot express."""
    assert classify("مُحَمَّد") == PARTIAL      # vowelled but no ending
    assert classify("اللّه") == PARTIAL         # shadda only
    assert classify("مِنْ") == PARTIAL          # ends in sukun, not a vowel


def test_sukun_and_shadda_alone_never_reach_full():
    """Shadda and sukun are marks, not i'rab. A word carrying only these has
    not answered the question the witness is being consulted for."""
    assert classify("مَدْرَسْ") == PARTIAL
    assert classify("اللّهْ") == PARTIAL


def test_tatweel_is_not_vocalisation():
    assert classify("محـمد") == NONE


# ------------------------------------------------------------- split_marks --

def test_split_marks_separates_skeleton_from_marks():
    letters, marks = split_marks("مُحَمَّدٌ")
    assert letters == "محمد"
    assert marks  # non-empty
    assert max(marks) == len(letters) - 1


def test_leading_mark_is_not_attached_to_a_nonexistent_letter():
    """A stray combining mark at position 0 must not crash or shift indices."""
    letters, marks = split_marks("\u064eمحمد")
    assert letters == "محمد"
    assert 0 not in marks or marks.get(0) == ""


# ----------------------------------------------------------- is_consistent --

def test_candidate_may_add_marks_the_source_omitted():
    assert is_consistent("مُحَمَّد", "مُحَمَّدٌ")
    assert is_consistent("مُحَمَّد", "مُحَمَّدٍ")
    assert is_consistent("محمد", "مُحَمَّدٌ")      # bare source constrains nothing


def test_candidate_may_not_contradict_a_supplied_mark():
    assert not is_consistent("مُحَمَّد", "مَحْمُود")


def test_partial_marks_rule_candidates_out():
    """The point of PARTIAL: it cannot choose, but it can eliminate."""
    cands = ["كِتَابٌ", "كُتُبٌ", "كَتَبَ"]
    survivors = [c for c in cands if is_consistent("كِتَاب", c)]
    assert survivors == ["كِتَابٌ"]


def test_different_skeletons_are_never_consistent():
    assert not is_consistent("كتاب", "كتب")


def test_tatweel_does_not_block_a_match():
    assert is_consistent("كِتـَاب", "كِتَابٌ")


# ------------------------------------------------------------------ agrees --

def test_agreement_is_exact_on_a_full_token():
    assert agrees("مُحَمَّدٌ", "مُحَمَّدٌ")
    assert not agrees("مُحَمَّدٌ", "مُحَمَّدٍ")


def test_mark_order_is_not_disagreement():
    """Shadda-then-fatha and fatha-then-shadda both occur in real files and
    encode the same reading. Counting that as a witness disagreement would
    manufacture a conflict statistic out of an encoding detail."""
    a = "مُحَم" + "\u0651\u064e" + "د"
    b = "مُحَم" + "\u064e\u0651" + "د"
    assert agrees(a, b)


def test_agreement_requires_the_same_skeleton():
    assert not agrees("كِتَابٌ", "كُتُبٌ")


# ------------------------------------------------------------ real corpora --

def test_configured_corpus_is_currently_bare(records):
    """A guard, not an assumption.

    Both configured texts are bare today, so Tier 0 must count zero. If this
    ever fails it means a source started arriving vowelled -- which is
    information, not breakage, and the failure should send you to the tier
    report rather than to this file.
    """
    vowelled = 0
    for rec in records["records"][:2000]:
        for ch in rec["textRaw"]:
            if classify(ch) != NONE:
                vowelled += 1
                break
    assert vowelled == 0
