# Diacritisation: what to adopt, and where it belongs

To be clear at the outset, since the phrasing in `GAPS.md` was loose: nothing
here proposes writing a diacritiser. The question is which existing one to adopt,
where it sits relative to the witness, and whether its output is good enough to
show a student at all.

---

## 1. We already have the evaluation set

This is the fact that makes the whole question decidable today rather than a
research project. **62,951 tokens in this corpus have their vowelling from an
aligned, fully-diacritised Bukhārī.** For vowelling specifically — not for roots
— the witness *is* ground truth, in the right register, at scale, already built.

Any candidate can therefore be scored in an afternoon. That is unusual and worth
exploiting before choosing.

## 2. What the candidates actually score

Measured on 5,434 witnessed tokens:

| | exact | right but for the case vowel | body wrong |
|---|--:|--:|--:|
| **witness** (aligned Bukhārī) | ~100% | — | — |
| **mishkal** — rule + statistical, GPL, on PyPI | **42.1%** | 27.1% | 30.8% |
| **farahidi** — as a by-product of analysis | 34.8% | 26.9% | 38.2% |

Some of the "wrong" is cosmetic and would lift with normalisation: `الْلَّهُ`
against `اللَّهُ`, `اللهِ` missing a shadda, `امرئ` returned bare. A generous
reading puts mishkal near 50% exact. It is still nowhere near a witness.

Two errors are worth naming because they are not cosmetic. mishkal reads
`سمعت` as `سَمِعَتْ` — third person feminine — where the witness has `سَمِعْتُ`,
first person; and it makes `الْأَعْمَالَ` accusative in
`إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ`, the exact error a reader caught in the
workbook. A general-purpose diacritiser reproduces the same class of mistake the
pipeline was corrected for.

## 3. Where it belongs

The hierarchy is right, and it fits the tier system already in place. Vowelling
precedence, best first:

1. **Corrections** — a human said so.
2. **Witness** — an aligned, diacritised edition of the parent text. 49.5%.
3. **Lexicon, unambiguous** — one candidate for the spelling. 45.8%.
4. **Rule-based inference** — collocation and case agreement. 2.1%.
5. **Generated** — a diacritiser. *New.*
6. **Most frequent reading** — a bare guess. 1.5%.

Generated sits above the frequency guess because 42% beats 71.3%… it does not.
**It sits BELOW it**, and that is the finding: on a corpus that *has* a workbook
and a witness, a general diacritiser is worse than every tier it could replace.
It should not be used at all there.

Its place is the corpus that has neither. There, tiers 2 through 6 do not exist —
there is no witness to align to and no corpus-specific lexicon — and the choice is
between generated vowelling and none.

## 4. The pedagogical objection, which is the real one

For a student practising reading, **wrong vowels shown confidently are worse than
no vowels.** Bare consonantal text asserts nothing; a wrong ḥaraka teaches an
error and does it with the authority of a printed edition.

At 42% exact, more than half the words on an unwitnessed page would be wrong.
That is not a hint, it is noise with a confident face.

So if generated vowelling ships, two things follow, and they are not negotiable:

- **Default to hidden.** The harakāt toggle already exists; on a generated
  corpus it should start *off*, inverting the current default. The reader asks
  for the hint rather than receiving it uninvited.
- **Marked at the word.** The dotted underline that currently marks a Tier 4
  guess should mark every generated vowel, and the panel should say plainly that
  the vowelling was generated and roughly how often that is wrong.

## 5. Pros and cons, plainly

**For adopting one**

- It is the only route to any vowelling at all on a text with no parent edition,
  and most books worth adding have no parent. Without it, "many books" means
  many *unvocalised* books.
- Even at 42%, a labelled hint helps a student who is stuck, in the way a
  dictionary's first sense helps: a starting point, not an answer.
- The evaluation is free and repeatable, so the claim never has to be taken on
  trust.
- Vowelling feeds morphology: a diacritised form constrains the analysis, so
  roots and iʿrāb improve downstream even where the vowel itself is not shown.

**Against**

- 42% exact means the majority is wrong. On a page of thirty words, seventeen
  carry an error.
- It reproduces the specific class of error this project has spent effort
  removing — case endings in constructions where the syntax is unambiguous.
- Another GPL dependency, and mishkal is from the same author as most of the
  stack, so its failure modes correlate with the tools we already use rather
  than being independent of them.
- Build cost, and the better candidates are heavier still.
- The honesty burden grows. Every additional derived layer is another thing the
  interface must explain, and the panel is already dense.

## 6. What has not been tried, and should be before deciding

mishkal is the *floor*, not the ceiling. It is rule-based with statistical
assistance, from 2014-era techniques. The current state of the art is
transformer-based and trained on **Tashkeela**, a 75-million-word corpus of
*classical* Arabic — which is the right register for ḥadīth, unlike the MSA news
corpora that most Arabic NLP is fitted to.

| candidate | licence | note |
|---|---|---|
| **CATT** (`abjadai/catt`) | Apache-2.0 | transformer, recent, reports low DER |
| **shakkelha** (`AliOsm/shakkelha`) | MIT | neural, with a published benchmark set |
| **Shakkala** | on PyPI | BiLSTM, classical + MSA |
| CAMeL Tools diacritizer | mixed | MSA-fitted; register mismatch |

If any of these scores materially above mishkal on our 62,951 witnessed tokens,
the calculus changes: at 80% exact a generated layer is a genuine aid, and at 95%
it is close to a witness. The cost is a heavier dependency — `torch` in CI — which
is a real but tractable price.

**The evaluation harness now exists and took twenty minutes to write.** Running
it against three more candidates is an afternoon, and it is the only responsible
way to choose.

## 7. Recommendation

1. **Do not ship mishkal.** On this corpus it is worse than what we have; on a
   new corpus it is below the bar where showing a vowel helps more than it harms.
2. **Score CATT and shakkelha on the witnessed tokens.** Same harness. If the
   best of them clears roughly 80% exact, adopt it as tier 5 for unwitnessed
   corpora only, hidden by default and marked at the word.
3. **If nothing clears the bar, ship unvocalised** and say so. A corpus that
   presents bare consonants and admits it is a better teaching tool than one that
   guesses at every vowel.

The measurement decides this. It should not be decided any other way.

## 8. Addendum (2026-08): the sunnah.com witnesses are already the ground truth

The record-link work on Bulūgh and the Shamāʾil settled a question this
document left open by implication: whether their vowelling should come from
sunnah.com "rather than" the current witnesses. It already does — the
witnesses ARE sunnah.com's text. The address-map derivation
(pipeline/sunnah_numbers.py) proved it mechanically: every one of the 402 +
1,767 witness entries is textually identical, under normalisation, to a
second scrape of the site at a pinned commit, and spot checks against live
pages match byte for byte. So wherever Tier 2 aligns — 99%+ of matn records
on both corpora, at median coverage 1.000 — the ḥarakāt a reader sees are
the site's own, and the tier order already prefers them over the lexicon and
every heuristic. There is no separate "adopt sunnah.com for vowelling"
workstream; it shipped the day those corpora bound.

One number in this repo invited the wrong conclusion and should not be read
that way again. Bulūgh's witness was recorded as "44% vowelled — the
thinnest witness here", which suggests a thin or stale scrape worth
replacing. Measured properly, it is neither: the witness wraps each matn in
braces, and INSIDE them — the text the reader binds and reads — 90.1% of
tokens carry a mark; the unvowelled mass is outside, in al-Albānī's takhrīj
apparatus (25.3% marked), which is equally unvowelled on the live site. The
bare tokens are bare at the source. Fetching a "better" witness would find
nothing better to fetch, and running a generated diacritiser over the
apparatus would be exactly the confident noise section 4 warns against —
the apparatus is an aside layer, not teaching text.
