"""
The join key between corpus tokens and the lexicon.

If this drifts, Phase 3 mis-binds silently: a token resolves to the wrong entry,
or to none, and nothing else in the build notices. It is asserted inside
lexicon.py too, but only there, and only on a full run.
"""

from normalise import normalise


def test_reproduces_every_search_key(surface):
    """All 22,464 rows, exactly. Not a sample, not a percentage."""
    bad = [
        (str(r["vocalized"]), str(r["search_key"]))
        for r in surface
        if normalise(str(r["vocalized"])) != str(r["search_key"])
    ]
    assert not bad, f"{len(bad)} of {len(surface)} mismatched, first: {bad[:3]}"


def test_hamza_fold_is_not_uniform():
    """
    The trap the spec calls out. Alef-seated hamza folds to bare ALEF; waw- and
    yeh-seated hamza fold to bare HAMZA. Folding them all to alef mis-joins
    about 600 forms and still looks plausible.
    """
    assert normalise("أ") == "ا"
    assert normalise("إ") == "ا"
    assert normalise("آ") == "ا"
    assert normalise("ؤ") == "ء"
    assert normalise("ئ") == "ء"
    assert normalise("ء") == "ء"


def test_letter_and_mark_folds():
    assert normalise("ى") == "ي"
    assert normalise("ة") == "ه"
    assert normalise("مُحَمَّدٌ") == "محمد"
    assert normalise("صَلَاةٍ") == "صلاه"


def test_typescript_twin_is_in_sync():
    """
    `web/src/lib/normalise.ts` is generated from this module. Two hand-kept
    copies would eventually disagree and the failure would be silent — a query
    that quietly matches nothing.
    """
    import subprocess
    from conftest import PIPELINE

    r = subprocess.run(
        ["python", str(PIPELINE / "codegen.py"), "--check"],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_root_key_folds_bare_hamza():
    """
    The workbook writes hamza-initial roots as ءرض and ءمر; a reader types أرض,
    which normalise() gives as ارض. Without this fold, root search for any
    hamzated word silently returns nothing.
    """
    from normalise import root_key

    assert root_key("أرض") == root_key("ءرض") == "ارض"
    assert root_key("أمر") == root_key("ءمر") == "امر"
    assert root_key("كتب") == "كتب"
    # Some root values carry stray punctuation, and the panel renders roots
    # spaced out as radicals.
    assert root_key("ح د ث") == "حدث"
    assert root_key("صلو.") == "صلو"
