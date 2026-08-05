# Gaps against the goals

An assessment of where the project falls short of what it is for: a multi-corpus
guided reader, many books, students practising Arabic, accuracy first even if
that means external tools, comprehensive word detail, pages that load fast.

Written after measuring. Where a figure appears it was produced today.

---

## 1. We compute the most valuable information and throw it away

This is the largest gap and the cheapest to close.

`farahidi` returns **twelve fields per token**. We keep **two**.

| field | example for `يَكْتُبُونَ` | kept? |
|---|---|---|
| `voweled_word` | يَكْتُبُونَ | ✗ |
| `case_or_mood` | **مرفوع** | ✗ |
| `part_of_speech` | فعل‖مضارع‖معلوم‖ثلاثي‖مجرد‖غائب‖هم | ✗ |
| `pattern_stem` | **يَفْعُلُونَ** | ✗ |
| `pattern_lemma` | **فَعَلَ** | ✗ |
| `proclitic` | ي‖حرف المضارعة | ✗ |
| `enclitic` | ون‖واو الجماعة والنون علامة الرفع | ✗ |
| `stem`, `diac_pattern_stem`, `priority` | | ✗ |
| `lemma`, `root` | كَتَبَ, كتب | ✓ |

For a student practising Arabic, **iʿrāb is the single most useful field on the
page** and we discard it. So is the wazn: knowing `يَكْتُبُونَ` is `يَفْعُلُونَ`
of form I is how a reader learns to parse the next verb rather than look it up.
The enclitic gloss — *واو الجماعة والنون علامة الرفع* — is a grammar lesson
attached to the word, in Arabic, already computed.

The panel currently shows meaning, root, lemma and Lane. It shows almost nothing
about **grammar**, which is what a reader of unvowelled classical prose is
actually stuck on.

## 2. There is no gold standard, so we do not know how accurate anything is

Every accuracy figure in this project is **agreement between two automated
sources**. Not one word has been checked by hand against a scholarly edition.

- "Normalisation reproduces 22,464/22,464" — reproduces the *workbook*.
- "Tier 3 is 97.2%, Tier 4 is 71.3%" — measured against the *witness*.
- "The analysers agree with the workbook on 92.3% of roots" — agreement, not
  accuracy.
- "Lane backs the workbook 1,489 to 214" — the best evidence here, and still a
  proxy.

So the honest statement is: we know how much the sources agree, and we know
where they disagree, and we do **not** know how often they are jointly wrong.
For a tool that teaches, that is the fundamental weakness. A hand-checked sample
of 300 tokens — vowelling, root, lemma, POS — would cost an afternoon and would
be the most valuable artifact in the repository.

The two errors found so far were both found by a reader, not by a test.

## 3. Vowelling does not generalise, and that blocks "many books"

| | share |
|---|--:|
| Witnessed from the aligned Bukhārī | 49.5% |
| A single lexicon candidate | 45.8% |
| Inferred or guessed | 3.6% |

**No source text carries any harakāt. Measured across a 179-text sample of
OpenITI — 120 random, plus 59 drawn from the genres where vocalisation is most
likely (poetry dīwāns, Qurʾānic sciences, Alfiyya commentaries, grammar) — not
one carried a single mark, with the detector verified at 98.7% on a known
vocalised control. That is 1.3% of the corpus, so the 95% upper bound on the
true rate is about 1.7%: rare, not impossible.

This is a fact about OpenITI specifically. The vocalised Bukhārī and Muwaṭṭaʾ
witnesses this pipeline already fetches are 98.7% vowelled, and a corpus taken
from Shamela directly, from Tanzil, or from a hadith dataset will arrive marked.
Tier 0 exists for that day and currently fires never.** Every vowel comes from the witness
or the workbook. A text with no parent edition therefore gets **no vowelling at
all** — and most books worth adding have no parent.

Measured today, `farahidi` can generate vowelling: **34.8% exact, a further
26.9% right except for the case vowel, 38.2% wrong**. Too weak to present as
authoritative on a witnessed corpus, and far better than nothing on one without.

No dedicated diacritisation model has been tried — Shakkala, CAMeL's diacritizer,
Mishkal, Farasa. This is the gap the goals name explicitly ("even if it requires
external tools for … harakat generation") and it is the one area where nothing
has been attempted.

## 4. Glosses are a single point of failure

The workbook is the **only** English gloss source in the project, it covers one
corpus, and no free Buckwalter/AraMorph package exists on PyPI. Every new text
therefore has **no glosses** — roots and Lane, but nothing that says what the
word means in English.

That is a hard wall against "many books", and it is not solved by any phase
currently planned. Options worth investigating: an OFL/CC-licensed
Arabic-English wordlist keyed by lemma, extracting glosses from Lane's own
entries, or licensing SAMA.

## 5. Build cost scales linearly and is already ten minutes

Per corpus, cold: analyse ~2.5 min, disambiguate ~5 min, segment/lexicon/bind
~1 min, build ~1 min. Ten books is roughly an hour and a half of CI, and a
change to the shared lexicon invalidates every corpus at once.

Nothing here is wrong yet. It will be at ten books, and the fix — per-corpus
caches keyed on that corpus's inputs, and incremental lexicon updates — is much
cheaper to design now than to retrofit.

## 6. The tests are Tajrīd-shaped — *pipeline half addressed*

> **Status:** the pipeline suite is split. `--corpus` selects the text under
> test; corpus pins live in `pipeline/tests/fixtures/{corpus}.yaml`; a missing
> pin skips with a message naming the key. Verified: 61/61 pass on tajrīd
> (unchanged), and on rawḍ the invariants run (43 pass) while the pins skip
> cleanly — which immediately caught one tajrīd assumption hiding in
> `test_tokenise.py`. The **browser suites remain tajrīd-shaped**; that is the
> remaining half of this item, due when the client becomes corpus-aware
> (MULTI-TEXT Phase 0.2).

61 pipeline tests and 243 browser assertions, and a large share are bound to this
one text: `hadith 38, word 48`; `عن X بن` must be majrūr; `إنما الأعمال` must be
marfūʿ; record counts of 2,550 and 3,255.

Those are good tests. But a second corpus will fail many of them **for the wrong
reason**, and the temptation will be to loosen them. They should be split now
into corpus-agnostic invariants (no residual markers, every reference resolves,
identifiers stable) and per-corpus fixtures that a new text supplies for itself.

## 7. Two files are too big to edit safely

`pipeline/build.py` is ~700 lines and does packaging, sharding, provenance
merging, search indexing and assertions. `WordPanel.tsx` is ~700 lines.

This is not an aesthetic complaint. In this session alone, three separate edits
to `build.py` silently failed because an anchor string did not exist, and one
introduced an ordering bug that only surfaced at runtime. A file that is hard to
edit correctly is a file that will accumulate quiet defects.

## 8. Validation is configured but not used — *addressed*

> **Status:** the browser gates now run on every build, push included; `deploy`
> waits only on `build`, so the SPEC §8 principle — no red gate between one
> maintainer and a deploy — still holds. See the amended SPEC §8 for the
> reasoning on record.

`SPEC.md` §8 records that browser gates run on pull requests. **Every change so
far has gone straight to `main`**, so those 243 assertions have never run against
a real change — only in the sandbox, on a copy, before delivery. The pipeline
tests do run on push, which is why the stale-figures and NaN regressions were
caught. The browser half is currently decorative.

## 9. Students have no way to report an error

The corrections layer exists and requires a git commit. The people best placed to
notice a wrong vowel are the readers, and there is no path from noticing to
fixing. Even a "this looks wrong" link that pre-fills an issue with the record id,
token index and current binding would turn every reader into a proofreader.

## 10. Panel latency has headroom but no budget

A panel currently costs three fetches: surface, stats, and classical + Lane.
Adding grammatical detail, cross-corpus occurrences and generated vowelling will
add more. The 100 ms budget is asserted in the build, but only for the current
shape; there is no test that fails when a *new* section adds a round trip.

---

## What I would do, in order

1. **Surface the morphology we already compute.** Case/mood, wazn, the clitic
   glosses. Largest gain for a student, no new dependency, no accuracy risk —
   it is already measured to the extent anything here is.
2. **Build a gold-standard sample.** 300 hand-checked tokens. Turns every
   existing figure from "agreement" into "accuracy" and makes item 3 decidable.
3. **Try a diacritiser**, gated on that sample. This is what unblocks books
   without a parent edition, and the goals name it explicitly.
4. **Split the tests** into invariants and per-corpus fixtures, before a second
   corpus forces it badly.
5. **Find a gloss source** that is not the workbook.

Items 1 and 2 are days. Items 3 and 5 are the ones that decide whether this
becomes a multi-book tool or stays an excellent single-book one.
