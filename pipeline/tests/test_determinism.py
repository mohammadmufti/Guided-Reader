"""
The pipeline must produce the same output from the same input.

This was not true. Two runs of identical code produced four differing tokens
in matn-02224, because `WitnessIndex.retrieve` summed IDF scores while
iterating a `set` of query terms: set order over strings depends on
PYTHONHASHSEED, float addition is not associative, and two rows within that
margin swapped places -- realigning a whole record to a different hadith.

It matters more than four tokens. A gate figure you cannot reproduce is not a
measurement, and a baseline you cannot reproduce makes regression testing
impossible -- which is exactly what happened when this was found, while trying
to prove that a refactor had changed nothing.
"""

import collections
import math
import random

from bind import WitnessIndex


def _index(rows):
    """Build a WitnessIndex without touching disk."""
    idx = object.__new__(WitnessIndex)
    idx.forms = [r.split() for r in rows]
    idx.norm = [r.split() for r in rows]
    df = collections.Counter()
    for row in idx.norm:
        df.update(set(row))
    n = len(idx.norm)
    idx.idf = {w: math.log(n / c) for w, c in df.items()}
    idx.postings = collections.defaultdict(list)
    for i, row in enumerate(idx.norm):
        for w in set(row):
            idx.postings[w].append(i)
    return idx


def test_retrieval_does_not_depend_on_query_term_order():
    """The direct cause. Shuffling the query must not move the result.

    Constructed so several rows score within float-rounding distance of each
    other, which is the situation the original code resolved by accident.
    """
    vocab = [f"w{i}" for i in range(40)]
    rows = [" ".join(random.Random(s).sample(vocab, 12)) for s in range(60)]
    idx = _index(rows)

    rng = random.Random(0)
    for trial in range(50):
        query = rng.sample(vocab, 14)
        first = idx.retrieve(list(query))
        for _ in range(8):
            shuffled = list(query)
            rng.shuffle(shuffled)
            assert idx.retrieve(shuffled) == first, (
                f"retrieval moved when the query was reordered (trial {trial})"
            )


def test_ties_break_on_row_index_not_insertion_order():
    """Two identical rows must always yield the same one.

    Without an explicit tie-break `max` returns whichever key was inserted
    first, and insertion order comes from the scoring loop.
    """
    idx = _index(["alpha beta gamma", "alpha beta gamma", "delta epsilon zeta"])
    rows = {idx.retrieve(["gamma", "beta", "alpha"])[0] for _ in range(20)}
    assert len(rows) == 1
    assert rows == {0}, "expected the lowest row index to win a tie"
