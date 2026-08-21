"""
The grammar fields Alkhalil returns, and the gold signal used to score them.
"""
from pathlib import Path

import pytest

import disambiguate as D
import eval_grammar as E

PIPELINE = Path(__file__).resolve().parents[1]


class _Result:
    def __init__(self, token, lemma, root, stem):
        self.token, self.lemma, self.root, self.stem = token, lemma, root, stem


class _Sol:
    def __init__(self, **kw):
        for k, v in kw.items():
            setattr(self, k, v)


def _analyser(solutions):
    class A:
        def analyze(self, _token):
            return solutions
    return A()


# ------------------------------------------------------------------ G-0


def test_absent_values_are_not_values():
    """Alkhalil writes `-` for an absent tag and `#` for an empty clitic slot.
    Kept, they put a bare dash in the panel and a meaningless bucket in every
    measurement over this file."""
    sol = _Sol(lemma="كَانَ", root="كون", stem="كُنْت", case_or_mood="-",
               part_of_speech="فعل|ماض|-|معلوم", pattern_stem="فَعَلْتُ",
               pattern_lemma="فَعَلَ", proclitic="#", enclitic="ت|تاء المتكلم",
               voweled_word="كُنْتُ")
    got = D.grammar_of(_Result("كُنْتُ", "كَانَ", "كون", "كُنْت"),
                       _analyser([sol]), {})
    assert "case_or_mood" not in got
    assert "proclitic" not in got
    assert got["tags"] == ["فعل", "ماض", "معلوم"]
    assert got["enclitic"] == "ت|تاء المتكلم"


def test_disagreement_yields_nothing():
    """Where the surviving solutions disagree on a field, the disambiguation
    did not settle it, and taking the first is taking one at random. This file
    feeds a panel that tells a student what case a word is in."""
    common = dict(lemma="رَجُل", root="رجل", stem="رَجُلَيْن",
                  part_of_speech="اسم", pattern_stem="فَعُلَيْنِ",
                  pattern_lemma="فَعُل", proclitic="#", enclitic="#",
                  voweled_word="رَجُلَيْنِ")
    sols = [_Sol(case_or_mood="مجرور", **common),
            _Sol(case_or_mood="منصوب", **common)]
    got = D.grammar_of(_Result("رَجُلَيْنِ", "رَجُل", "رجل", "رَجُلَيْن"),
                       _analyser(sols), {})
    assert "case_or_mood" not in got, "an unsettled case was reported anyway"
    assert got["pattern_lemma"] == "فَعُل", "fields that DO agree must survive"


def test_the_context_chosen_reading_is_the_one_read():
    """Out of context the first solution is frequently wrong — that is why the
    disambiguation stage exists. So the reading is selected by what the
    disambiguator kept, not by position."""
    wrong = _Sol(lemma="كُتّاب", root="كتب", stem="كُتّاب", case_or_mood="مرفوع",
                 part_of_speech="اسم", pattern_stem="فُعّال", pattern_lemma="فُعّال",
                 proclitic="#", enclitic="#", voweled_word="كُتّابٌ")
    right = _Sol(lemma="كِتَاب", root="كتب", stem="كِتَاب", case_or_mood="مجرور",
                 part_of_speech="اسم", pattern_stem="فِعَال", pattern_lemma="فِعَال",
                 proclitic="#", enclitic="#", voweled_word="كِتَابٍ")
    got = D.grammar_of(_Result("كِتَابٍ", "كِتَاب", "كتب", "كِتَاب"),
                       _analyser([wrong, right]), {})
    assert got["case_or_mood"] == "مجرور"
    assert got["pattern_lemma"] == "فِعَال"


def test_root_and_lemma_are_still_written():
    """G-0 must not change what already existed."""
    src = (PIPELINE / "disambiguate.py").read_text(encoding="utf-8")
    assert '"root": result.root' in src and '"lemma": result.lemma' in src


# ------------------------------------------------------------------ G-1


def test_a_past_tense_verb_is_not_scored_for_case():
    """It is MABNI on fatha. Scoring it as mansub measures our gold, not the
    analyser — worth 15 points on the verb figure."""
    assert E.gold_for("قَالَ", {"فعل", "ماض"})[0] is None
    assert E.gold_for("اذْهَبْ", {"فعل", "أمر"})[0] is None


def test_the_five_verbs_are_marfu_by_the_nun():
    """al-af`al al-khamsa keep the nun to show raf`, and that nun carries
    fatha. Read as a case vowel it says mansub, so يُخَالِفُونَ scores wrong
    while being right — 169 false errors in a 400-record slice."""
    assert E.gold_for("يُخَالِفُونَ", {"فعل", "مضارع"}) == (
        "مرفوع", "verb: al-af`al al-khamsa")
    assert E.gold_for("يَتَفَكَّرُونَ", {"فعل", "مضارع"})[0] == "مرفوع"


def test_sukun_is_not_a_case_on_a_noun():
    """It marks waqf or an indeclinable form."""
    assert E.gold_for("الْبَيْتْ", {"اسم"})[0] is None
    assert E.gold_for("يَذْهَبْ", {"فعل", "مضارع"})[0] == "مجزوم"


def test_a_dual_marks_case_on_its_suffix():
    assert E.gold_for("رَجُلَانِ", {"اسم", "مثنى"})[0] is None


def test_particles_are_not_scored():
    assert E.gold_for("فِي", {"حرف"})[0] is None


def test_ordinary_nouns_are_scored_from_the_printed_vowel():
    assert E.gold_for("كِتَابٌ", {"اسم"}) == ("مرفوع", "noun")
    assert E.gold_for("كِتَابًا", {"اسم"}) == ("منصوب", "noun")
    assert E.gold_for("بِكِتَابٍ", {"اسم"}) == ("مجرور", "noun")


def test_a_verb_is_never_majrur():
    assert E.gold_for("يَذْهَبِ", {"فعل", "مضارع"})[0] is None


# ------------------------------------------------------------------ G-2


def test_only_the_four_iraab_values_ship():
    """Anything else is a bug upstream, and passing it through would put an
    unknown string in front of a student."""
    import build

    assert build.IRAAB == {"مرفوع", "منصوب", "مجرور", "مجزوم"}
    counter = {"iraab": 0, "withheld": 0}
    emit = build.make_iraab(
        {
            "r:0": {"case_or_mood": "مجرور"},
            "r:1": {"case_or_mood": "مبني"},     # not an i`rab
            "r:2": {"case_or_mood": "-"},        # absent
            "r:3": {"lemma": "x"},               # unsettled
        },
        counter,
    )
    assert emit("r", 0, "بِكِتَابٍ") == {"iraab": "مجرور"}
    assert emit("r", 1, "بِكِتَابٍ") == {}
    assert emit("r", 2, "بِكِتَابٍ") == {}
    assert emit("r", 3, "بِكِتَابٍ") == {}
    assert emit("r", 99, "بِكِتَابٍ") == {}
    assert counter["iraab"] == 1


def test_nothing_is_claimed_where_the_ending_is_bare():
    """
    The gate, and the measurement behind it.

    Alkhalil does NOT infer i`rab from syntax — it READS the printed mark.
    Masking the mark on the last consonant, so it cannot see the thing it is
    scored on:

        ending visible   n=1,681   accuracy 96.1%
        ending masked    n=  140   accuracy 52.1%

    Coverage falls twelvefold and accuracy falls to a coin toss. So where the
    ending is bare the analyser is guessing, and we say nothing.
    """
    import build

    counter = {"iraab": 0, "withheld": 0}
    emit = build.make_iraab({"r:0": {"case_or_mood": "مجرور"}}, counter)
    assert emit("r", 0, "بكتاب") == {}, "an i`rab was claimed on a bare ending"
    assert counter["withheld"] == 1
    assert emit("r", 0, "بِكِتَابٍ") == {"iraab": "مجرور"}


def test_ending_detection_reads_the_last_consonant():
    import build

    assert build.ending_is_vowelled("بِكِتَابٍ")
    assert build.ending_is_vowelled("كِتَابًا"), "tanwin fath precedes a final alif"
    assert build.ending_is_vowelled("يَذْهَبْ"), "sukun can be a jussive marker"
    assert not build.ending_is_vowelled("كتاب")
    # vowelled inside, bare at the end — the common case in a partly pointed
    # edition, and exactly the one to withhold on
    assert not build.ending_is_vowelled("كِتَاب")


def test_iraab_is_on_the_token_not_the_entry():
    """Case belongs to a position, not to a word. The same form is marfu` in
    one hadith and majrur in the next, so it cannot live in the shared surface
    entry that every occurrence points at."""
    import contracts

    assert "iraab" in contracts.Token.__annotations__
    assert "iraab" not in contracts.PanelEntry.__annotations__


def test_the_unmeasured_tags_are_not_shipped():
    """Alkhalil's derivational tags — اسم فاعل, جامد, لازم/متعد — leave no
    trace in the vowelling, so eval_grammar.py cannot score them and nothing
    else has. مضاف looked measurable and FAILED: the printed text agrees it
    carries no tanwin, but that test is circular, and the real test — is the
    following token majrur — held in only 63.3% of cases with a predicted
    case."""
    import contracts

    for field in ("tags", "mudaf", "pattern_stem", "pattern_lemma"):
        assert field not in contracts.Token.__annotations__, (
            f"{field} is shipped but nothing has measured it"
        )


def test_every_built_corpus_is_disambiguated():
    """
    i`rab is a word-panel feature, so it belongs to every book we serve.

    THE BUG THIS PINS. The workflow ran `disambiguate.py --corpus tajrid` and
    nothing else, and cached `build/tajrid/disambiguated.json` alone. build.py
    degrades quietly when the file is missing — it emits no `iraab` and says
    nothing — so the feature would have shipped for one corpus out of nine with
    a green build. That is the same shape as the dictionaries shipping empty:
    a stage that is optional for a good reason, and a workflow that forgot to
    call it.
    """
    import re

    wf = (PIPELINE.parent / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )
    built = set(re.findall(r"python pipeline/build\.py\s+--corpus (\w+)", wf))
    analysed = set(re.findall(r"python pipeline/disambiguate\.py --corpus (\w+)", wf))
    missing = sorted(built - analysed)
    assert not missing, (
        f"these corpora are built but never disambiguated, so their word "
        f"panels would carry no i`rab: {missing}"
    )


def test_the_disambiguation_cache_covers_every_corpus():
    """Caching one book's analysis is why it was one book's feature."""
    wf = (PIPELINE.parent / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )
    assert "pipeline/build/*/disambiguated.json" in wf, (
        "the context cache names a single corpus again"
    )


def test_disambiguation_runs_after_binding():
    """It reads bind.py's vocalised surfaces. Run before, it sees the raw
    source, which OpenITI strips for twelve of thirteen corpora — measured at
    71.4% accuracy against 97.1%."""
    import re

    wf = (PIPELINE.parent / ".github" / "workflows" / "deploy.yml").read_text(
        encoding="utf-8"
    )
    for corpus in re.findall(r"python pipeline/disambiguate\.py --corpus (\w+)", wf):
        bind = wf.find(f"pipeline/bind.py    --corpus {corpus}")
        dis = wf.find(f"pipeline/disambiguate.py --corpus {corpus}")
        build = wf.find(f"pipeline/build.py   --corpus {corpus}")
        assert bind != -1 and dis != -1, corpus
        assert bind < dis, f"{corpus}: disambiguate runs before bind"
        if build != -1:
            assert dis < build, f"{corpus}: disambiguate runs after build"
