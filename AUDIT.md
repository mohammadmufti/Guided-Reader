# Audit and second-corpus work

What changed, what was measured, and what was found wrong. Ordered so that the
findings come before the work they motivated, because in most cases the
measurement is the argument.

Every figure here was produced by running the pipeline, not estimated.

---

## Bugs found

### 1. The pipeline was not reproducible

`WitnessIndex.retrieve` summed IDF scores while iterating `set(query)`. Set
order over strings depends on `PYTHONHASHSEED`, float addition is not
associative, and two witness rows within that margin swapped places — which
realigned a whole record to a different hadith.

Two runs of **identical, untouched code** produced four differing tokens in
`matn-02224`.

It is four tokens in 127,163, so the published figures were substantially
right. What was wrong is that they were unfalsifiable. A gate you cannot
reproduce is not a measurement, and a baseline you cannot reproduce makes
regression testing impossible — which is how this was found, while trying to
prove a refactor had changed nothing.

Fixed with `sorted(set(query))` and an explicit tie-break on row index.
Verified across differing hash seeds: zero differing tokens. Pinned by
`tests/test_determinism.py`.

**This fix stands alone and belongs on `main` regardless of everything else
here.** It is two lines.

### 2. `--corpus` scoped output only

`lexicon.py` and `bind.py` accepted `--corpus` and used it to choose an output
directory, while reading `Tajrid_frequency_tables.xlsx` and
`sahih_bukhari_vocalised.csv` as literals. `lexicon.py --corpus rawd` therefore
wrote al-Tajrīd's lexicon into `build/rawd/`, and `build.py` consumed it without
complaint.

Nothing crashed. A geographical dictionary bound against a hadith collection
mostly falls to Tier 5, so the symptom was a failing coverage gate — which reads
as "the line grammar needs work", not "you are binding the wrong book".

It survived because CI only ever ran those stages on `tajrid`; `rawd` stopped at
segmentation. A corpus that is only ever segmented only ever proves
segmentation.

`lexicon.py` also carried `EXPECTED_COVERAGE`, `EXPECTED_AMBIGUITY` and
`EXPECTED_DIVERGENCE` as module constants — seventeen figures measured from
al-Tajrīd on 2026-07-26, indexed as `EXPECTED_COVERAGE[field]`. A second corpus
would not merely fail the gate; it would `KeyError` on a field name.

### 3. `unvocalized` was the vocalised form on every minted entry

`mint_from_witness` stored the fully vowelled string in `unvocalized`, which is
supposed to be dediacritised-but-hamza-preserving — what the Review sheet and
the interface key on, and not `search_key`, which folds those letters too.

Invisible until two independent derivations of the same `match_id` were
compared: `share.py` refused to merge and named the field. Every minted entry in
both corpora had it wrong.

### 4. `build.py` deleted the whole payload

`shutil.rmtree(DATA)` on every run. Building a second corpus silently replaced
the first and `index.json` became a different book. No error, no warning.

### 5. Smaller

- `tokenise.py` compiled `(بخاري: N)` as a literal and applied it to every
  corpus before any config was read — the last text-specific Arabic string in
  the shared token path. `segment.py` already read the same pattern from
  `segmentation.editorial_reference`; the two are now one.
- `build.py` did `e["lane_root"]` as a hard subscript on a field only
  `lexicon.py` computes, so any derived lexicon crashed. Absent classical
  apparatus is a legitimate state.
- `WordPanel.tsx` told every reader the vowelling came "from a fully vocalised
  edition of Bukhārī" — false on any other corpus.
- Sources cached to one flat directory keyed only by a filename the yaml author
  chooses, so two corpora picking the same name overwrote each other and the
  checksum guard then blamed the wrong text.

---

## Measurements

### The harakāt question

The original worry — that ground-truth vowelling was stripped during
normalisation — is unfounded, and provably so. The sources carry none.

| | tokens | vocalised |
|---|--:|--:|
| al-Tajrīd | 130,459 | 0 |
| al-Rawḍ | 311,861 | 0 |
| Muwaṭṭaʾ, all 9 versions | — | 0 |
| **179-text OpenITI sample** | — | **0** |

The sample was 120 random plus 59 from the genres where vocalisation is most
likely. Detector verified at 98.7% on a known vocalised control. 95% upper bound
on the true rate: ~1.7%.

`tokenise.py` preserves marks in `raw` and `reconstruct()` asserts losslessness,
so nothing is lost at tokenisation either. What was missing was a *tier*: the
surface resolved witness → lexicon → raw, so a source haraka was reachable only
for a token that bound to nothing. Tier 0 fixes that and currently fires never.

### Position and inventory are different questions

Removing al-Tajrīd's workbook dropped it from 97.2% to 80.6%, unbound 0.0% →
16.8%. That looked like the workbook was load-bearing.

But 17,548 distinct unbound keys for 19,987 tokens — almost all hapax, spread
evenly at 13.6% per record — and **98.0% of them are words that do occur in the
vocalised Bukhārī, elsewhere**. Adding seven more vocalised collections moved
that only to 99.5%. They were not missing. Record-level retrieval never reached
them.

Aligning a record gives POSITION — this reading, here, in context: Tier 2.
Reading the witness as a TYPE LEXICON gives INVENTORY — the set of vowellings a
spelling is known to take, which is what Tiers 1, 3 and 4 choose among. Only the
first needs alignment.

With `seed_from_witness`:

| al-Tajrīd | workbook | workbook-free |
|---|--:|--:|
| Tier 1+2 on matn | 97.2% | 96.6% |
| unbound | 0.0% | 0.3% |
| bound and glossed | — | 97.0% of matn |
| lemma / root / pos | — | 99.1% / 51.1% / 99.1% |

The workbook's structural contribution is **0.6 points**. What it holds that
nothing else does is meaning: 21,028 curated glosses and the divergence
analysis. That is scholarship, not computation.

### Cross-corpus lexical overlap

`match_id` is `stable_id(search_key, vocalized)` — derived from the form, never
from frequency — so an entry is corpus-independent by construction.
`ARCHITECTURE.md` claimed this; nothing had spent it.

| Muwaṭṭaʾ reading | readings | matn tokens |
|---|--:|--:|
| exact match in al-Tajrīd's workbook | 3,980 | 89.5% |
| …already glossed there | 3,881 | **89.0%** |
| same spelling, different vowelling | 973 | 6.9% |
| not in al-Tajrīd at all | 1,023 | 3.7% |

So a Muwaṭṭaʾ reader shows a meaning for **73.0% of its running text** with no
new lexicography.

### Retrieval coverage detects the wrong edition

The Muwaṭṭaʾ's nine OpenITI versions are not nine digitisations. They are
different *riwāyāt*, and the retrieval median says so:

| version | recension | median |
|---|---|--:|
| Shamela0001699 | Yaḥyā al-Laythī | **0.963** |
| JK000466 | — | 0.912 |
| Shamela0016050 | al-Shaybānī | 0.617 |
| Shia000901Vols | — | 0.429 |

A low median means "wrong edition" before it means "broken pipeline". Recorded
as `gates.min_retrieval_median`.

### Numbering has no external witness

sunnah.com lists 61 books; we segment 61 kitāb, same order, same titles.

But sunnah.com's "Arabic reference" is itself a running count — Book 4 Hadith 1
is Arabic reference 223, where ours makes it 217. The drift is not missing
hadith: our per-kitāb numbering is gapless against the file (book 1 = 1–30,
book 2 = 1–115, book 3 = 1–70). sunnah.com gives book 1 thirty-**two**. It is
numbering a different printed edition.

And the printed numbers are not unique: **six duplicates**, including hadith 13
three times over in Kitāb al-Ḥajj.

So `displayNumber` is an ADDRESS, not a citation — it matches no printed edition
and a reader who cited it would be citing us. `editionNumber` plus its kitāb is
what gets shown, because that is what every external reference uses and what
resolves.

### Morphology

`build/morphology/analyses.json` has never existed in any run. For al-Tajrīd
that is nearly invisible; for a minted corpus it is the only source of
morphology, and its absence took the Muwaṭṭaʾ's root coverage to 31.6% of bound
matn tokens, all of it borrowed from a donor. Root drives "other forms of this
root", so that navigation was dead for two-thirds of clickable words and looked
like a working feature.

`bind.py` now warns; CI fails on the missing file.

Note the per-entry figure is 39.1% and the per-token figure 31.6%. Entry counts
flatter the result because donors overlap at the head of the distribution. Only
the token figure describes what a reader meets.

---

## Architecture

### The workbook is one text's exception

`Tajrid_frequency_tables.xlsx` is hand-built for one text and there will be no
equivalent for the next. It should keep being used for al-Tajrīd — it is that
book's best evidence and 0.6 points better than the derived path. It should not
be built into the pipeline, because one text's exceptional input becomes every
text's problem the moment a shared module knows a sheet name.

`pipeline/workbook.py` is now the only module that parses it. `Lexicon` takes
plain row dicts and cannot tell where they came from. A test walks every module
and fails if `read_excel` or a sheet name appears outside the allowlist.

The flag that drives the three behavioural branches is `curated`, not
`from_workbook`: a future corpus might be curated from something that is not a
spreadsheet.

### Enrichment is not contamination

Donors and the shared glossary may say what a word MEANS. They may never
introduce a reading the alignment did not independently produce, and they carry
no frequency — `glossary.py` has an explicit `REFUSE` list, and `share.py`
touches only surface shards, never statistics.

The proof it is safe: tier counts are byte-identical with and without donors.

### Tiers are a pipeline, not interchangeable strategies

The obvious refactor is a `Resolver` per tier chained in order. It would be
wrong. Tier 2's alignment mints entries that Tiers 1 and 4 read; the collocation
table Tier 3 votes with is built from Tier 1–2 output across every record; the
repair pass rewrites a Tier 2 binding into a Tier 3 one. They share mutable
state by design.

What IS per-token and independent: Tiers 0, 1, 3-case and 4. Those are the
extraction candidates if `bind.py` grows further. The alignment and the repair
are not. Written down in `tiers.py` so it does not have to be rediscovered.

### Line grammar stays config, not subclasses

`TajridSegmenter` / `MuwattaSegmenter` would destroy the property worth having.
The Muwaṭṭaʾ added two config keys — `section_levels` (the file states its own
hierarchy) and `opener_on` (the number sits on a body line, not a section line)
— and no branch anywhere names a text. The thing to watch is the mode-flag
count; those were the fourth and fifth.

---

## Verification

al-Tajrīd, compared token by token against untouched `main` (with the
determinism fix applied to both, or the comparison is meaningless):

```
2,550 records, 127,163 tokens
  surface 0   matchId 0   tier 0
  confidence 0   clickable 0   binding 0
```

Schema changes are the two deliberate renames (`bukhariRefs` → `crossRefs`,
`workbookIndex` → `curatedIndex`) plus `displayNumber` and `editionNumber`.
No functionality removed.

---

## Still open

- **`analyses.json` cannot be built in a sandbox** — `camel-tools` needs a
  separate `camel_data` download. CI guards it.
- **al-Musawwā is not in OpenITI.** Confirmed against the full 13,364-record
  metadata index, not inferred. Shāh Walī Allāh has six works there; neither
  al-Musawwā nor the Persian al-Musaffā is among them. Getting it means Shamela
  and your own mARkdown conversion — a corpus-acquisition project.
- **The Muwaṭṭaʾ has no curated lexicography of its own.** 73.0% gloss coverage
  is borrowed. The 1,023 readings absent from al-Tajrīd and the 973 that share a
  spelling but not a vowelling are where new work would go, and the frequency
  distribution says the head is cheap: 1,000 readings cover 71.5% of matn.
- **Two `max(votes.items())` tie-breaks in `bind.py`** (collocation and repair)
  resolve on insertion order. Deterministic today because construction order is,
  but not explicitly so.
