"""
Identifier stability.

`match_id` was `{search_key}#{n}` where n ranked homographs by frequency IN THIS
CORPUS. Adding a second text shifts frequencies, reorders n, and renames
identifiers — measured at 14.5% of ids pointing at a different form.

Nothing broke at the time, because deep links address token positions. But a
shared cross-corpus store, occurrence links and saved words all need a key that
survives a rebuild, so the discriminator is now derived from the form itself.
"""

from lexicon import stable_id


def _mapping(rows, scheme):
    if scheme == "stable":
        return {stable_id(str(r["search_key"]), str(r["vocalized"])): r["vocalized"] for r in rows}
    out, groups = {}, {}
    for r in rows:
        groups.setdefault(str(r["search_key"]), []).append(r)
    for key, grp in groups.items():
        for n, r in enumerate(sorted(grp, key=lambda x: -x["freq"]), 1):
            out[f"{key}#{n}"] = r["vocalized"]
    return out


def test_ids_survive_a_frequency_shift(surface):
    """
    The test that matters, and the one an earlier version got wrong: comparing
    SETS of ids showed 0 renamed under both schemes, because the set of
    `{key}#{n}` strings is unchanged by reordering. What changes is which FORM
    each id points at.
    """
    perturbed = [dict(r) for r in surface]
    freqs = [r["freq"] for r in surface][::-1]
    for r, f in zip(perturbed, freqs):
        r["freq"] = f

    base_new, pert_new = _mapping(surface, "stable"), _mapping(perturbed, "stable")
    base_old, pert_old = _mapping(surface, "ordinal"), _mapping(perturbed, "ordinal")

    moved_new = sum(1 for k, v in base_new.items() if pert_new.get(k) != v)
    moved_old = sum(1 for k, v in base_old.items() if pert_old.get(k) != v)

    assert moved_new == 0, f"{moved_new} stable ids moved"
    assert moved_old > 0, "the ordinal scheme should be unstable — check the fixture"


def test_no_collisions(surface):
    ids = {stable_id(str(r["search_key"]), str(r["vocalized"])) for r in surface}
    assert len(ids) == len(surface), f"{len(surface) - len(ids)} collisions"


def test_id_carries_its_search_key(surface):
    """The client routes a lookup to a shard by hashing the part before '#'."""
    for r in surface[:500]:
        mid = stable_id(str(r["search_key"]), str(r["vocalized"]))
        assert mid.rsplit("#", 1)[0] == str(r["search_key"])
