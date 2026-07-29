# Roadmap

> **Shipped since v1:** **B.1** (stable identifiers) and **A.2** (full Lane
> ingest), together with **E.2** (payload-derived shard counts), which A.2
> required. Their entries below are kept for the record and marked ✅.

Work not in v1, in the same phased form as `SPEC.md`: each item states what it
is, why it is worth doing, how to do it, what would prove it worked, and what it
risks breaking. Every figure below is measured against the shipped build.

Items are ordered by dependency, not by appeal. Track B in particular is a
prerequisite for most of what follows it, and doing Track A first would mean
doing part of it twice.

---

## Principles for future work

These are the lessons v1 paid for. They should govern anything added later.

**1. Do not destroy information upstream to save work downstream.** The
classical apparatus is the clearest failure of this in the current build. The
workbook's extraction *sampled* one Lane sense and discarded the rest, and once
that choice was made it could not be recovered — the reader is stuck being told
that ṣalāh means "the middle of the back of a human being." The pipeline should
carry the full source and let the presentation layer make selection visible as a
choice. This is the same rule as "preserve nulls", applied to prose.

**2. The fix for a bad sample is not a better sample.** It is to stop sampling.
Ranking senses by relevance is legitimate *if the ranking is shown as a
heuristic and the full entry stays reachable*. Silently picking a better one
reproduces the original error with more confidence.

**3. New capability enters as a new binding tier, with a measured error rate.**
The tier system already carries provenance end to end and the interface already
renders it. A morphological analyser, a second lexicon, an alignment against a
different edition — each becomes a tier with its own held-out accuracy, not a
silent improvement to an existing one.

**4. Identifiers must be stable before anything depends on them.** See B.1.

**5. Budgets are per-request, not per-file.** Shard counts should be derived
from a target bytes-per-shard, not fixed. Track A breaks the current fixed 16.

---

## Track A — The classical apparatus: stop sampling

### A.0 What is actually wrong

Measured against the shipped payload:

| | |
|---|--:|
| Roots with classical material | 1,829 |
| Mean senses in the full Lane entry | **15.8** |
| Maximum senses in one entry | **56** |
| Senses the reader is shown | **1** |
| Characters shipped per root | 81 |
| Characters sitting unused in `classical_senses_more` | 507 |

So roughly **94% of the classical material is discarded**, and the one sense that
survives was chosen mechanically rather than for relevance. The panel is honest
about this — it labels the line *not the definition of this word* — but honesty
about a bad answer is a mitigation, not a fix.

`classical_senses_more` already holds six times more text than we show, and the
current build does not render it at all. That is the cheapest possible first
step.

### A.1 Render what we already have — *small*

Show `classical_senses_more` behind progressive disclosure: keywords, then the
sampled sense, then "more senses from Lane" expanding the rest. No new source,
no new pipeline stage, no contract change beyond adding one field back to the
shipped shard.

*Gate:* the ṣalāh panel shows prayer-related senses without the reader having to
leave the page. Panel latency unchanged.

*Risk:* low. The field is already in `lexicon.json`; it was dropped at packaging.

### A.2 Ingest Lane properly — *large* — ✅ SHIPPED

Replace the extracted fragments with a structured Lane keyed by root. Lane's
*Arabic-English Lexicon* (1863–1893) is public domain; digitised forms exist
with sense structure preserved.

Store per root: an ordered list of senses, each with its text, Lane's own sigla
(K, TA, S, M, Msb) resolved to source names, and the sense's position in the
entry. Keep the sigla — they are provenance, and a student who learns to read
them gains something.

**Efficiency.** This is the part that needs planning rather than enthusiasm.
Projected from the current payload at 15.8 senses per root:

| | current | projected full Lane |
|---|--:|--:|
| Classical payload, raw | 1.82 MB | ~29 MB |
| Classical payload, brotli | 0.45 MB | **~7.0 MB** |
| Per shard at the current 16 shards | 29 KB | **428 KB** |

428 KB per shard blows the 100 ms first-panel budget. **Shard count must become
a function of payload size**, targeting a fixed bytes-per-shard — roughly 114
shards at a 60 KB budget. Make that a build parameter computed from the emitted
bytes, not a constant, so the next content change does not silently regress
latency.

A second efficiency note: full entries make the *cold* path unchanged (nothing
classical is in the cold load) but make the *first panel on a new root* more
expensive. Consider splitting each root into a "head" shard (keywords + top
senses, ~60 KB total) fetched with the panel, and a "tail" shard fetched only
when the reader expands. That keeps the common case at today's cost.

*Gate:* every root that had classical material still has it; no root loses
senses; per-shard brotli size within the configured budget; first-panel latency
still under 100 ms measured end to end, including a cold root.

*Risk:* **contained**, and this is worth noting as an architectural win. The
classical apparatus is already isolated behind `lane_root` → its own shard set.
Replacing its contents touches no record, no binding, and no reading-pane code.
The Phase 4 boundary turned out to be in the right place.

### A.3 Rank senses without pretending — *medium*

With the full entry available, order senses by a defensible signal: overlap with
`gloss_msa`, overlap with the curated `technical_sense`, and Lane's own ordering
as a tiebreak. Show the ranking as a ranking — "most likely relevant here" —
with the entry's original order one click away.

*Gate:* on the 2,539 forms with a curated literal/technical pair, the top-ranked
Lane sense agrees with the curated technical sense more often than Lane's first
sense does. That is a measurable claim; if it fails, ship the entry unranked.

*Risk:* this is the item most likely to violate principle 2. If the ranking
cannot be shown to beat "Lane's own order", it must not ship — an unranked
entry is a fine outcome.

---

## Track B — A corpus-independent lexicon

### B.0 The problem

The lexicon *is* the Tajrīd workbook. A second text will contain words that are
not in it, and they will bind at Tier 5 — inert, not clickable, no panel. For
al-Tajrīd that is 12 tokens. For an unrelated text it could be 40%.

The workbook also conflates two kinds of fact, and they have different
lifetimes:

- **Corpus-specific** (8 fields): `freq`, `pct`, `cum_pct`, `rank`, `doc_freq`,
  `layers`, `first_record`, `kwic`. These are properties of *this text*.
- **Corpus-independent** (23 fields): the form→lemma→root chain, POS, glosses,
  the Lane apparatus, curated senses, divergence. These are properties of
  *Arabic*.

Splitting them makes adding a corpus additive: a new text contributes new
lexical entries to a shared store and gets its own statistics, instead of
requiring a whole parallel workbook.

### B.1 Make `match_id` stable — *small, and blocking* — ✅ SHIPPED

**This must happen first.** `match_id` is `{search_key}#{n}` where `n` ranks
homographs by descending frequency **in this corpus**. Adding a second corpus
shifts frequencies, which reorders `n`, which renames identifiers. Measured:
**6,502 of 22,464 ids would be renamed** by a frequency shift.

Nothing in v1 breaks from this today, because deep links address token positions
(`?w=12`) rather than lexicon entries. But every plausible next feature —
"other occurrences of this word", saved words, cross-corpus links, stable
citation — depends on a lexicon key that does not move.

Replace the ordinal with something derived from content: `{search_key}#{h}`
where `h` is a short hash of the vocalised form. Frequency then determines
*display order* only, which is what it was always for.

*Gate:* rebuild twice with deliberately perturbed frequencies; every `match_id`
identical. A corpus added to the store renames nothing.

*Risk:* one-time invalidation of every shard URL. Do it before anything depends
on the ids, not after. Ship a `schemaVersion` in `index.json` at the same time
so a stale client degrades visibly instead of silently mis-resolving.

### B.2 Split the store — *medium*

```
lexicon/                     shared, grows as corpora are added
  entries/{shard}.json       keyed by stable match_id — the 23 lexical fields
  classical/{shard}.json     keyed by lane_root
corpora/{id}/
  stats/{shard}.json         keyed by match_id — the 8 corpus fields
  records/, hadith/, search.json
```

The panel composes a `LexicalEntry` with a `CorpusStats` at render time. The
"In this corpus" section can then honestly name which corpus, and — later —
compare across them.

**Usability gain worth calling out:** once statistics are per-corpus, the panel
can say *"7 times here, 1,240 times across the collection"*, which is far more
useful to a learner than a bare rank. That is not extra data; it is the same
data, correctly factored.

*Gate:* the Tajrīd build is byte-identical in what it displays. Adding a second
corpus adds entries without modifying existing ones — assert that the shared
store is append-only for unchanged forms.

*Risk:* a contract change. Do it behind `codegen.py` so the TypeScript cannot
drift, keep the fnv1a shard routing unchanged so URLs keep their meaning, and
land it in the same release as B.1 to spend the invalidation once.

### B.3 Cover unseen forms — *large*

For a new text, forms absent from the shared store need analysis. Run a
deterministic morphological analyser (CAMeL Tools, Alkhalil, Farasa) as a
**new binding tier**, not as a silent backfill.

This does not violate "never fabricate linguistic data". An analyser is a tool
with a measurable error rate, not a model inventing an answer — the rule exists
to prevent unmeasured guesses being presented as facts. So: measure it the same
way Tier 3 and Tier 4 were measured, hold out tokens that Tier 2 resolved, and
publish the number in `LIMITATIONS.md`.

Slot it between collocation and frequency fallback, since it should beat a bare
frequency prior and not beat a witnessed alignment.

*Gate:* held-out accuracy measured on ≥ 20k tokens and stated in the app.
Analyser-derived entries are visually distinguishable in the panel and carry
their own provenance line.

*Risk:* the largest in this document. An analyser that is 80% right across 40%
of a new text puts a lot of confident-looking wrong data in front of students.
It must enter as its own tier with its own caveat, and if its accuracy lands
below Tier 4's 69.9% it should not ship at all.

---

## Track C — Binding improvements

### C.1 Use the Review candidates — *small, and the best value in this document*

The `Review` sheet carries a candidate list for every ambiguous form, and the
binder never looks at it. Measured on the shipped build:

| | |
|---|--:|
| Tier 4 tokens (the guesses) | 2,277 |
| Of those, with an unused candidate list | **2,013 (88%)** |
| Mean candidates listed | 3.8 |

Tier 4 currently takes the most frequent candidate and is **69.9%** correct.
The Review list narrows the field to 3.8 options with reference-corpus
frequencies attached — a strictly better prior than a bare corpus-frequency
ranking, on 88% of the cases where it matters.

*Gate:* held-out accuracy of the new rule measured the same way; must beat
69.9%. If it does not, revert — the measurement is the deliverable either way.

*Risk:* low. Isolated to `bind.py`; the tier structure and the interface are
unchanged. Note that the candidate frequencies are from the reference corpus,
not this one, so treat them as a prior and not as counts.

### C.2 Reduce the `pos_agreement = disagree` population — *medium*

15,334 tokens carry the workbook's own flag that the root may be wrong,
concentrated on hollow and irregular verbs. The panel warns about them, which is
right, but 12% of tokens carrying a warning is a lot of warning.

A second analyser used as a tiebreak — where two of three agree, drop the flag —
would shrink it. Same rule as everything else: measure before and after, publish
the number.

### C.3 Close the last segmentation gaps — *small*

Two known, both documented rather than fixed:

- 19 lines in the second corpus use `%~%` as a verse hemistich separator outside
  a `#` prefix (0.07% of lines). Their text is captured but counted as prose.
  Verse should be modelled, not flattened — a dictionary and a poetry anthology
  both need it.
- Residual per-layer token deltas against the workbook: `frontmatter` −45,
  `heading_bab` −46, `matn` +45. Extraction is verified lossless, so these are
  boundary differences in the workbook's own segmentation. Worth resolving only
  if a future workbook is generated by this pipeline rather than supplied.

---

## Track D — Reader features

### D.1 Other occurrences of this word — *small, now nearly free*

Deferred in v1 because it needed a reverse index. Phase 10 built one. The search
index maps `search_key` → records; extending postings to `(record, tokenIndex)`
pairs makes exact occurrence links possible.

Cost: postings grow from 94,404 to ~127,000 — the index goes from roughly
150 KB to perhaps 250 KB brotli, still one lazily-fetched file.

Depends on B.1 if occurrences are to be addressed per lexicon entry rather than
per spelling.

*Usability note:* this is probably the single most requested thing a student
would want and the cheapest remaining item. It turns the panel from a dictionary
into a concordance.

### D.2 Root search — *small*

Search currently matches surface forms, and the empty state has to explain that
"كتب will not find مكتوب". Since 51.9% of tokens carry a root, a root index is a
second small posting list and closes the most obvious gap in search.

### D.3 A real self-test mode — *medium*

The harakat toggle is currently all-or-nothing. The data supports something
better: hide the vowels, let the reader commit to a reading word by word, then
reveal — and grade against the binding, showing confidence honestly (*"we are
also unsure about this one"*). That is a genuinely novel use of the provenance
data and is the feature most specific to what this product knows.

### D.4 Offline — *small*

The payload is static, content-addressed and immutable, which is the ideal case
for a service worker. Cache `index.json` plus visited hadith and shards; the
existing offline banner already handles the state.

---

## Track E — Infrastructure

### E.1 A tabular intermediate — *small*

`lexicon.json` is 49 MB raw as a pipeline artifact and is loaded whole by three
later stages. Parquet or SQLite would cut both memory and time, and would make
the shared store of B.2 practical to query incrementally.

### E.2 Payload-derived shard counts — *small, prerequisite for A.2* — ✅ SHIPPED

Replace the fixed 64/16 shard constants with a target bytes-per-shard computed
at build time, and assert the resulting maximum shard size against the latency
budget. Without this, A.2 silently regresses first-panel latency by 10×.

### E.4 The preview artifact is a second implementation — *medium* — ✅ RETIRED

`preview_template.jsx` reimplements the reading pane, the word panel, the
controls and search as a single self-contained file, so the work can be shown
without serving 3,132 files. It is **hand-maintained and drifts**: every feature
added to the real components has had to be written twice, and nothing enforces
that the two agree.

Either generate it from the real components at build time, or retire it in
favour of deploying the actual static site somewhere previewable. The second is
probably right — the payload is static and immutable and wants a CDN, not a
bundler.

### E.3 CI — *small* — ✅ SHIPPED (pipeline tests on every build; browser gates on pull requests)

`codegen.py --check`, the pipeline gates, and the four e2e suites all run
headless already. Nothing enforces them between changes.

---

## Sequencing

```
B.1 stable match_id ─┬─> B.2 split store ──> B.3 unseen forms
                     └─> D.1 occurrences
E.2 shard budgets ────> A.2 full Lane ─────> A.3 sense ranking
A.1 render what we have        (independent, do first)
C.1 Review candidates          (independent, do first)
```

**Do first, in this order:** C.1 and A.1. Both are small, both are measurable,
and both improve what a student sees without touching an interface contract.
C.1 in particular has the best ratio in this document — it should reduce the
error rate on 88% of the corpus's worst-bound tokens using data already in the
build.

**Do next:** B.1, before anything depends on identifier stability. It is cheap
now and expensive later.

**Do not start A.2 before E.2.** Shipping full Lane entries onto a fixed
16-shard layout would put 428 KB behind a 100 ms budget.

---

## Deliberately not on this list

Translation, commentary, audio, user accounts. Each would be a different
product. The thing this build is good at is telling a reader exactly how much to
trust what it is showing them, and every item above either extends that or gets
out of its way.
