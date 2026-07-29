"""
Recover the stem of a form whose morphological analysis kept only a clitic.

THE PROBLEM. 409 forms in this corpus carry `pos=particle`, `lemma=لِ` (or
`سَ`, or in one case a bare shadda) and no root, because the supplied analyser
latched onto a proclitic and discarded the word. `وَلْيُحَدِّثْ` — "and let him
relate" — is recorded as a particle with no root, while its own gloss reads
`and + for + him/it to + cause;bring about`, a verb.

THE FIX, AND WHY IT NEEDS NO EXTERNAL ANALYSER. The stem is usually attested
elsewhere in the very same corpus, correctly analysed. `يحدث` is in the lexicon
with `pos=verb, lemma=حَدَّثَ, root=حدث`; `يبايع` with root `بيع`. So strip
candidate clitics and look the residue up in our own lexicon.

That matters for more than convenience. Nothing is invented: a recovered root is
one that some other row of the same workbook already asserts for the same stem.
The alternative — running a third-party analyser — introduces a second opinion
with its own error rate and no way to check it against anything here.

WHAT IT WILL NOT DO. It does not touch a form that already has a root, and it
does not guess when the stem is unattested (`يفقدون` is not in this corpus, so
`سَيَفْقِدُونَنِي` stays unrecovered). Silence is the correct output there.
"""

from __future__ import annotations

from dataclasses import dataclass

from gloss import parse_gloss

# Applied to NORMALISED forms, since that is how the lexicon is keyed. Ordered
# longest-first so the most specific match is tried before a shorter prefix that
# happens to be a substring of it.
PROCLITICS = sorted(
    [
        "",
        # single
        "و", "ف", "ل", "ب", "ك", "س",
        # article, and article with a preposition or conjunction
        "ال", "وال", "فال", "بال", "كال", "لل", "ولل", "فلل",
        # conjunction + particle
        "ول", "فل", "وب", "فب", "وس", "فس", "وك", "فك",
        # conjunction + article + preposition
        "وبال", "فبال", "وكال", "فكال",
        # future and interrogative
        "سي", "سن", "ست", "سا", "او", "اف",
    ],
    key=len,
    reverse=True,
)

ENCLITICS = sorted(
    [
        "",
        "ه", "ها", "هم", "هن", "هما", "همء",
        "ك", "كم", "كن", "كما",
        "ي", "ني", "نا",
    ],
    key=len,
    reverse=True,
)

MIN_STEM = 3  # an Arabic root is at least three radicals


@dataclass
class Recovered:
    root: str
    lemma: str | None
    pos: str | None
    stem: str
    source_match_id: str
    proclitic: str
    enclitic: str
    stem_freq: int
    corroborated: bool


class Recoverer:
    """
    Looks a stripped stem up in the corpus's own lexicon.

    `entries` maps a search_key to the rows sharing it. Only rows that HAVE a
    root and are not themselves particles can serve as evidence — recovering a
    particle from a particle would restate the problem.
    """

    @staticmethod
    def _stem_senses(row: dict) -> list[str]:
        g = parse_gloss(row.get("gloss_msa"))
        return g["senses"] if g else []

    @staticmethod
    def _sense_words(senses: list[str]) -> set[str]:
        return {
            w
            for sense in senses
            for w in "".join(c if c.isalpha() else " " for c in sense.lower()).split()
            if len(w) > 2
        }

    def __init__(self, entries: dict[str, list[dict]]) -> None:
        self.by_key: dict[str, dict] = {}
        for key, rows in entries.items():
            usable = [
                r for r in rows
                # `r["root"]` is NOT a sufficient test: a pandas NaN is a float
                # and floats are truthy, so every root-less row was passing this
                # filter and being offered as evidence with root=nan.
                if isinstance(r.get("root"), str) and r["root"].strip()
                and r.get("pos") not in (None, "particle", "pronoun")
            ]
            if not usable:
                continue
            # Only accept a stem whose rows AGREE on the root. Normalisation
            # merges genuine homographs — جنة and جنى both become جنه, and أرض
            # collides with the imperative of رضي — and a stem that means two
            # things is no evidence at all. This is most of the residual error.
            roots = {r["root"] for r in usable}
            if len(roots) != 1:
                continue
            self.by_key[key] = max(usable, key=lambda r: r.get("freq") or 0)

    def _corroborates(self, row: dict, want: set[str]) -> bool:
        """
        Does the candidate stem MEAN roughly what the input's gloss says?

        The last class of error is genuine ambiguity that no length or
        uniqueness test can catch: stripping `ال` off `الأرض` leaves `ارض`,
        which is also the imperative of رضي. Arabic alone cannot separate them.
        The English gloss can — "earth, land" shares no vocabulary with "be
        content". Two independent signals agreeing is a much stronger claim than
        either alone.
        """
        if not want:
            return False
        return bool(want & self._sense_words(self._stem_senses(row)))

    def recover(
        self,
        key: str,
        *,
        unvocalized: str | None = None,
        n_proclitics: int | None = None,
        n_enclitics: int | None = None,
        stem_senses: list[str] | None = None,
        require_corroboration: bool = True,
        exclude_self: bool = True,
    ) -> Recovered | None:
        """
        Strip candidate clitics and return the best attested stem.

        Stripping blind is not good enough — it takes the ك off `كِتَابِ` and
        turns root كتب into توب. So the gloss constrains it: `gloss_msa` already
        segments the word, and `n_proclitics`/`n_enclitics` say how many affixes
        there actually are. If the gloss says none, none are stripped.

        `unvocalized` guards the other systematic error: normalisation folds
        ة to ه, so `الجنة` looks like it ends in an object pronoun. It does not.

        Preference order: the LONGEST surviving stem, then the most frequent —
        the analyser gives up ground reluctantly, because over-stripping is how
        a form collides with an unrelated root.
        """
        ends_in_ta_marbuta = bool(unvocalized) and unvocalized.rstrip().endswith("ة")
        want_senses = self._sense_words(stem_senses or [])
        best: Recovered | None = None
        for pro in PROCLITICS:
            if pro and not key.startswith(pro):
                continue
            if n_proclitics is not None:
                # The gloss counts slots, not letters, so one slot may be `وال`.
                # What it can say with certainty is whether there are any.
                if n_proclitics == 0 and pro:
                    continue
                if n_proclitics > 0 and not pro:
                    continue
            rest = key[len(pro):]
            for enc in ENCLITICS:
                if enc and not rest.endswith(enc):
                    continue
                if n_enclitics is not None:
                    if n_enclitics == 0 and enc:
                        continue
                    if n_enclitics > 0 and not enc:
                        continue
                if enc == "ه" and ends_in_ta_marbuta:
                    continue
                stem = rest[: len(rest) - len(enc)] if enc else rest
                if len(stem) < MIN_STEM:
                    continue
                if exclude_self and stem == key:
                    continue
                row = self.by_key.get(stem)
                if row is None:
                    continue
                cand_senses = self._sense_words(self._stem_senses(row))
                corroborated = bool(want_senses and (want_senses & cand_senses))
                if require_corroboration and not corroborated:
                    continue
                cand = Recovered(
                    root=str(row["root"]),
                    lemma=str(row["lemma"]) if row.get("lemma") else None,
                    pos=row.get("pos"),
                    stem=stem,
                    source_match_id=str(row["match_id"]),
                    proclitic=pro,
                    enclitic=enc,
                    stem_freq=int(row.get("freq") or 0),
                    corroborated=corroborated,
                )
                if best is None or (len(cand.stem), cand.stem_freq) > (
                    len(best.stem),
                    best.stem_freq,
                ):
                    best = cand
        return best
