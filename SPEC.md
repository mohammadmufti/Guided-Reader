# Build spec — a word-by-word reader for a classical Arabic corpus

**Revision 2.** Revision 1 was written before the build; this one is written
after it, and every figure in it has been measured against the actual data.
Places where revision 1 was wrong are marked **[CORRECTED]** with what was
believed, what is true, and how it was established. Those corrections are the
most valuable part of this document: each one cost real time to find, and most
of them would have shipped silently as plausible-looking wrong answers.

---

## 1. What this is

A reading surface for **al-Tajrīd al-Ṣarīḥ li-aḥādīth al-Jāmiʿ al-Ṣaḥīḥ**,
al-Zabīdī's abridgement of Ṣaḥīḥ al-Bukhārī. One hadith on screen; click any
word to see its vowelling, transliteration, root, lemma, modern gloss, the
classical apparatus, and — where the classical and modern senses have parted
company — the distance between them.

The audience is a student who can read Arabic but cannot yet read *this*: who
knows the alphabet and basic grammar but stalls on unvowelled classical prose,
on ḥadīth register, and on words whose technical sense has drifted from the
everyday one.

### Requirements

1. One hadith on screen at a time. Navigation by previous/next, jump-to-number,
   a kitāb/bāb browser, and full-text search.
2. Every word individually addressable and annotatable.
3. Arabic text on the left of the page; the apparatus on the right. On narrow
   screens the apparatus becomes a bottom sheet, never a stack below the fold.
4. Nothing is presented as more certain than it is. Every reading carries its
   provenance and the interface says when it is guessing.
5. Nulls are meaningful. "This word has no root" is an answer; "we failed to
   find one" is a different answer; the interface must never conflate them.
6. Swapping the text must be easy. Every corpus-specific assumption lives in
   configuration, not code.

### Deliberately out of scope

Translation, commentary, audio, user accounts, saved words, "other occurrences
of this word" (needs a reverse index over positions rather than records — cheap
to add on top of the search index built in Phase 10, deliberately not built).

---

## 2. Sources

### 2.1 The text

OpenITI mARkdown, 1,418,201 bytes:

```
https://raw.githubusercontent.com/OpenITI/0900AH/master/data/
  0893IbnAhmadZaynDinSharji/0893IbnAhmadZaynDinSharji.TajridSarih/
  0893IbnAhmadZaynDinSharji.TajridSarih.Shamela0096283-ara1
```

The bare URI **is** the file. This text has no `.completed` or `.mARkdown`
sibling; appending an extension 404s. Author died 893 AH, so the work is public
domain. The edition encoded is Muʾassasat al-Risāla, Damascus, 1430/2009.

### 2.2 The vocalisation reference

A fully diacritised Ṣaḥīḥ al-Bukhārī, 8,067,734 bytes:

```
https://raw.githubusercontent.com/abdelrahmaan/Hadith-Data-Sets/master/
  All%20Hadith%20Books/Sahih%20Bukhari.csv
```

**[CORRECTED]** Revision 1 gave a path that 404s. The directory name contains
spaces and must be percent-encoded; the repo has 31 blobs and two Bukhārī
files, and the one *with* tashkīl is `Sahih Bukhari.csv` (8.1 MB), not
`Sahih Bukhari Without_Tashkel.csv` (4.5 MB). Found by walking
`/repos/abdelrahmaan/Hadith-Data-Sets/git/trees/master?recursive=1`.

**[CORRECTED — important]** Revision 1 assumed this file could be indexed by
hadith number. **It cannot.** It has 7,008 rows while al-Tajrīd's own
cross-references run to 7,563, and testing every offset from −2 to +2 gives a
flat ~24% token overlap with no peak — the row order does not track the standard
numbering at all. The counterpart must be *retrieved by content*. See Phase 3.

The repo carries no licence. Use it as an alignment reference only; do not
redistribute Bukhārī text in the output payload.

### 2.3 The lexicon workbook

A user-supplied `.xlsx`, 11 sheets. Copy it into the cache so the pipeline has a
checksummed, immutable input rather than reaching outside the repo.

| Sheet | Rows | What it is |
|---|--:|---|
| README | 36 | The workbook's own notes. Read them. |
| Summary | 13 | Headline figures. **Two of them are wrong — see §3.4.** |
| Lookup | 7 | Field definitions |
| Surface | 22,464 | One row per vocalised surface form. The main table. |
| Lemma | 7,239 | Dictionary forms |
| Root | 2,189 | Content words only |
| Unvocalized | 18,960 | Undiacritised form → search key |
| Divergence | 3,313 | Lemmas whose classical and modern senses differ |
| TechnicalSenses | 86 | Hand-curated literal/technical pairs |
| Names | 333 | Proper nouns mined from isnād patterns |
| Review | 3,349 | Forms whose vowelling was a fallback |

---

## 3. What the data actually says

Every figure below was measured. Where revision 1 disagreed, both are given.

### 3.1 Structure of the text

- 18,830 body lines after the `#META#Header#End#` marker.
- Three line kinds: `### | …` structural (2,711), `# …` paragraph (7,686),
  `~~…` wrap-continuation (8,432).
- **Exactly one structural level.** `### ||` never occurs. The kitāb/bāb
  hierarchy is therefore *not encoded* and must be inferred.
- 2,253 numbered openers covering hadith 1–2254.
- 88 zawāʾid additions, 92 kitāb headings, 115 bāb headings, 1 frontmatter block.
- Editorial noise: 2,552 `PageV..P..` markers (2,342 of them the null
  `PageV00P000`), 468 `ms###` manuscript markers, 2,551 Shamela `<div>` tags,
  164 `[ص: N]` page brackets.

### 3.2 Three things revision 1 got wrong about the structure

**[CORRECTED] There are no missing hadith numbers.** Revision 1 said ~13 were
absent. Its regex missed openers carrying an embedded manuscript marker —
`### | 95 ms024 - ` — and undercounted by twelve. The true count is 2,253
openers over 1–2254 with a single apparent gap at 1202, and that gap is not
real: the source line reads `### | 1201 - 1202 - `, two hadith sharing one
opener. There is no boundary in the text to split on, so the record covers both
numbers and both resolve to it. **Every number 1–2254 resolves.**

**[CORRECTED] The zawāʾid note is not a record.** Revision 1 defined a
`zawaid_note` record type on the assumption that the note line is the unit. It
isn't. A zawāʾid addition is an *unnumbered hadith body* introduced by a `•`
bullet; the note that follows ("this hadith is an addition of al-Ḍiyāʾ
al-Dāghistānī…") is the same sentence all 88 times and merely terminates it.
The proof is the token count: the workbook assigns 6,063 tokens to the zawāʾid
layer and treating the *bodies* as the records reproduces 6,063 exactly.

**[CORRECTED] There are five layers, not four.** Revision 1's `layer` enum
omitted `heading_kitab`. The workbook's `first_record` column uses five
namespaces and its `layers` column names all five.

### 3.3 The kitāb/bāb hierarchy must be inferred

With one structural level and no nesting, the level of each heading has to be
derived. It cannot be done lexically on the word `باب`: in Kitāb al-Maghāzī
chapters are named by battle (`غزوة أحد`), in Kitāb al-Tafsīr by Qurʾānic verse
(`قوله عز وجل: {…}`).

The working rule: **a heading beginning `كتاب` or `أبواب` is book-level;
everything else is a chapter of the book above it.** That rule reproduces the
workbook's `heading_kitab` token tally exactly, 224 = 224, and produces 92 books
in Bukhārī's canonical order.

### 3.4 The record-ID convention

`first_record` values look like `matn-00005`. **The numeric suffix is a global
record sequence in reading order**, not a per-type counter — which is why
`zawaid-02638` exceeds the 2,254 hadith count, and why `heading_kitab` reaches
2626 when there are only 92 book headings.

The workbook's pipeline emits **one extra, empty record after each kitāb
heading** not already followed by a bāb heading. Adding those phantoms yields
exactly 2,640, the workbook's maximum, with 98.5% namespace agreement. The
phantom's type is unobservable — no form ever first-occurs in one — which is
what confirms it is empty.

Recommendation: keep a clean record sequence and carry the workbook index
alongside as a separate field. Do not put 91 empty records into the reading
order to match a foreign convention.

### 3.5 Tokenisation

**The workbook's tokenisation is not documented anywhere and a naive whitespace
split overshoots by 12.6%.** It:

1. strips the editorial `(بخاري: N)` cross-references, and
2. counts only tokens containing at least one Arabic letter — so the bare
   dashes in `- رضي الله عنه -`, footnote digits and stray punctuation are not
   tokens.

That reproduces the per-layer tallies to within 46 tokens in 127,207 (0.036%),
with `zawaid` and `heading_kitab` matching exactly.

| layer | tokens |
|---|--:|
| matn | 119,077 |
| zawaid | 6,063 |
| heading_bab | 970 |
| frontmatter | 873 |
| heading_kitab | 224 |
| **total** | **127,207** |

### 3.6 Coverage, all verified

| Field | Token coverage | Types |
|---|--:|--:|
| `gloss_msa` present | 98.2% | 21,028 |
| `root` present | 51.9% | 18,894 |
| `classical_keywords` present | 50.8% | 18,226 |
| curated literal/technical pair | 11.8% | 2,539 |
| `morph_confidence = exact_with_case` | 67.7% | 17,361 |
| `pos_agreement = agree` | 70.4% | 17,752 |
| `voc_source` begins `aligned` | 90.0% | 16,969 |

Divergence, token-weighted: `not_applicable` 47.6%, `aligned` 16.8%, `curated`
11.8%, `developed_sense` 9.0%, `no_msa_gloss` 8.2%, `divergent` 5.6%,
`no_classical_entry` 1.1%.

Ambiguity: 18,593 distinct search keys, 2,631 of them ambiguous, accounting for
49.7% of all tokens. Always taking the most frequent candidate is correct for
85.9% of tokens — that is the number any binding strategy must beat.

### 3.7 Two figures in the Summary sheet are wrong

**`Tokens covered by root table: 0`** is a bug. The real figure is 65,986
tokens, **51.9%**, matching the workbook's own coverage table.

**`Tokens in matn layer: 124,885`** matches nothing computable. Forms occurring
*only* in matn give 36,973; forms occurring in matn *at all* give 125,926; the
actual matn token count from the `layers` column is 119,077. The `layers` column
is self-consistent — it sums to exactly the stated total of 127,207 — so trust
it and treat the Summary figure as a second independent bug.

### 3.8 Two undocumented facts about the workbook

**The `Review` sheet is keyed by `unvocalized`, not `search_key`.** In a
2,000-row sample, 1,997 keys resolve against `Surface.unvocalized` and only
1,346 against `search_key`. Normalising before lookup loses a third of the sheet
silently.

**Review is a disambiguation table, not just a flag list.** It carries
`n_candidates` and a parsed candidate set with frequencies for all 3,349
ambiguous forms. Those frequencies come from the *reference* corpus, not this
one — `أبي` occurs 190 times here but its top candidate is tagged 5433.

### 3.9 The normalisation — and the trap in it

`search_key` is the join key between corpus tokens and the lexicon. Derive it
from character-frequency arithmetic rather than from prose; the counts fix every
rule with no guesswork:

```
ا  13,009 -> 17,483   (+4,474 = أ 3,963 + إ 303 + آ 208)
ي   7,526 ->  7,999   (  +473 = ى 473)
ه   4,821 ->  6,763   (+1,942 = ة 1,942)
ء     462 ->  1,069   (  +607 = ئ 439 + ؤ 168)
```

Strip harakat, tanwīn, shadda, sukūn, superscript alef and tatweel; then fold
letters.

**[CORRECTED] The hamza rule is not uniform.** Revision 1 said "hamza forms
unified", which reads as though all hamza-bearing letters fold together. They do
not: **alef-seated hamza (أ إ آ) folds to bare ALEF; waw- and yeh-seated hamza
(ؤ ئ) folds to bare HAMZA.** Folding ؤ and ئ to alef instead mis-joins roughly
600 forms while still looking plausible.

Assert the implementation against all 22,464 rows before proceeding.

---

## 4. Architecture

```
pipeline/                    Python. Runs offline, emits static JSON.
  corpora/{id}.yaml          EVERY corpus-specific assumption
  fetch.py                   checksummed, idempotent acquisition
  segment.py                 mARkdown -> records, config-driven
  normalise.py               the join key
  lexicon.py                 workbook -> lexicon.json + indices
  gloss.py                   Buckwalter glosses -> renderable structure
  bind.py                    five-tier token binding
  build.py                   -> web/public/data/, sharded and compressed
  contracts.py               SINGLE SOURCE OF TRUTH for data contracts
  codegen.py                 emits the TypeScript twins; --check fails on drift
  build/{corpus}/            intermediate artifacts, namespaced per corpus
web/                         Vite + React + TypeScript + Tailwind
  public/data/               the shipped payload
  src/                       components, routes, lib
  e2e_phase*.py              gate checks, run against a real browser
```

Generate rather than duplicate. Anything defined in two languages —the data
contracts, the normalisation function — is written once in Python and emitted
to TypeScript by `codegen.py`, with `--check` failing the build on drift. Two
hand-maintained copies of a normalisation table will eventually disagree, and
the failure is silent: a query that quietly matches nothing.

---

## 5. Data contracts

Full definitions live in `pipeline/contracts.py`. The load-bearing points:

- **Nulls are preserved end to end.** `root: string | null` means a null root is
  a real answer — particles and proper nouns have none — not a missing value.
  Never widen to optional, never default to `""`.
- **`CorpusRecord`, not `Record`.** A contract type named `Record` silently
  shadows TypeScript's `Record<K,V>` utility for every importing file, and the
  failure surfaces far from the cause. `codegen.py` refuses to emit any name
  that collides with a TypeScript global.
- **`RecordType`** is `hadith | kitab | bab | frontmatter`. Revision 1's fifth
  value `zawaid_note` is removed — see §3.2.
- **`Layer`** is `matn | zawaid | heading_bab | heading_kitab | frontmatter`.
- Records carry `seq` (our clean sequence), `workbookIndex` (the foreign
  convention, for resolving `first_record` and `kwic`), `numbersCovered`,
  `tokens`, `zawaidNote`, and `bukhariRefs`.
- Tokens carry `binding` (`unique | aligned | heuristic | unbound`) and
  `confidence` (`high | medium | low | none`). These are not decoration; they
  decide whether a word is clickable and whether its panel carries a caveat.
- `leading + Σ(surface + punctuationAfter)` must reproduce a record's text
  exactly. That property is what lets the reading pane wrap every word in its
  own element without disturbing Arabic shaping.

---

## 6. Phases

Execute one at a time. Stop at each gate. Report the numbers the gate asks for.
Do not proceed on a failed gate by narrowing the criterion.

### Phase 0 — Scaffold and contracts

Scaffold `pipeline/` and `web/`. Commit the contracts. Write `fetch.py`:
download to `pipeline/cache/`, checksum, refuse re-download when the checksum
matches, and fail loudly if a cached file's hash has changed.

**Use one manifest per corpus** (`manifest-{id}.json`). A single shared manifest
makes a second corpus impossible without deleting the first.

*Gate:* `npm run dev` serves a styled shell. `fetch.py` retrieves and checksums
every source and is idempotent. Contracts committed and typechecking.

### Phase 1 — Corpus segmentation

mARkdown → `records.json`. Parse the metadata header. Fold `~~` continuations
into the line they continue. Classify each structural line. Strip markers,
**in the configured order** — manuscript markers occur *inside* both the div
tags and the page brackets, so whichever can nest must go first. Attach kitāb
and bāb context. Build reading order and the number index.

*Gate:* Every display number resolves. Kitāb/bāb counts reported and eyeballed
against the printed TOC. No residual `PageV`, `ms###`, `[ص:`, `###`, `<div` or
`~~` in any record — assert it. Token sum within ±2% of the workbook's, using
the workbook's tokenisation (§3.5). Three records printed in full.

### Phase 2 — Lexicon extraction

Workbook → `lexicon.json` plus indices. Preserve nulls. Build the search-key
index with homographs ordered by descending frequency.

*Gate:* The normalisation reproduces **22,464/22,464** `search_key` values.
Every coverage and ambiguity figure in §3.6 reproduced to one decimal, types
included. Five entries round-tripped and printed in full: a particle, a proper
noun, a curated technical term, a root-less form, a hapax.

Expect `lexicon.json` to be large (49 MB raw). The classical apparatus is a pure
function of `lane_root` — 1,829 roots, zero conflicting payloads — so it
deduplicates 9.8× at packaging time. Measure it here; deduplicate in Phase 4.

### Phase 3 — Token binding

Five tiers, each measured separately. The point is not to bind everything but to
be honest about how each binding was arrived at.

1. **unique** — the search key resolves to exactly one surface form. 50.3%.
2. **aligned** — resolved against the diacritised Bukhārī. 46.0%.
3. **heuristic (medium)** — resolved by rule. 2.0%.
4. **heuristic (low)** — the most frequent candidate. A guess. 1.8%.
5. **unbound** — no lexicon entry. 12 tokens in the whole corpus.

**[CORRECTED] Tier 2 retrieves its counterpart; it cannot look it up.** See
§2.2. Build an IDF-weighted inverted index over rare tokens in the Bukhārī rows
and retrieve the best-matching row per record. That achieves a median token
overlap of 0.959 on 2,338 of 2,342 records. The `(بخاري: N)` cross-reference —
carried by 2,222 of 2,254 hadith — then *corroborates* the retrieval rather than
driving it.

Two failure modes to guard against, both found the hard way:

- **Alignment can land in an isnād.** A size-1 matching block on a word that
  occurs several times in the Bukhārī hadith with different case endings is not
  positionally determined. One `رضي الله عنهما` had its vowelling transferred
  from `عبدُ اللهِ` five tokens away in an isnād.
- **Errors certify themselves.** Tier 3's strongest rule is agreement with the
  same collocation elsewhere in the corpus, learned from tiers 1 and 2. If
  positionally-undetermined bindings are allowed to vote, a systematic alignment
  error becomes its own evidence. Exclude them from the evidence table.

*Gate:* Tier-by-tier coverage, token-weighted. **Tier 1+2 ≥ 90% of matn
tokens.** Per-tier error rates. Cross-check against the `Review` sheet.

On measuring error rates: a 100-token manual sample cannot resolve a 2% effect.
Tier-2 tokens have an independent witness, so hide it and ask what the lower
tiers would have said. That measures Tier 3 at **97.2%** and Tier 4 at **69.9%**
on 55,728 tokens.

On the Review cross-check: measure it **per form against a base rate**, not
token-weighted. The sheet's 3,349 forms cover 87% of ambiguous tokens by mass,
so a handful of very frequent words swamp the token view and it shows nothing.
Per form, flagged forms are +27.5 points enriched in the fallback tier against a
55.5% base — which is the clustering the gate is looking for.

**[CORRECTED] The workbook is not ground truth.** Agreement with its binding is
96.1%, but some of the disagreement is the workbook being wrong. Its split of
`الله` between nominative and genitive is 4,586:4,279; conditioning on the
preceding word against the vocalised Bukhārī — which is categorical, `صلى الله`
10,901:0 nominative, `رسول الله` 0:5,770 genitive — shows the correct ratio is
much higher, and that removing isnāds should push it *up* from Bukhārī's 1.40,
not down to 1.07. Treat 96.1% as a floor on accuracy, not a ceiling.

### Phase 4 — Data build and packaging

Emit `index.json`, one `hadith/{id}.json` per record, sharded lexicon, and
precompressed `.gz`/`.br` siblings.

Deduplicate the classical apparatus by `lane_root` (13.4 MB → 1.4 MB). Drop
`kwic` and `first_record` from the shipped payload — they verify binding and the
reading pane never touches them. Parse the Buckwalter glosses here, once, so the
raw string never reaches the client at all.

Cache headers: the *content* is immutable but the *filenames* are not, so
`Cache-Control: immutable` alone serves stale data forever after a rebuild. Put
a content hash in `index.json` as `buildId`, have the client append
`?v={buildId}` to every hadith and shard request, and let `index.json` itself
revalidate.

*Gate:* Cold load of one hadith **< 150 KB** including the index. A word-panel
lookup for a word not yet fetched resolves **< 100 ms** — measure it end to end
in a browser, not by arithmetic. No orphans in either direction; every bound
`match_id` resolves in the shard it hashes to.

Do not compress `index.json` by encoding record IDs as layer codes. It saves
7 KB against a 150 KB budget and a 27 KB worst case, and costs readability plus
a decode step. Measure before optimising.

### Phase 5 — Shell, routing, navigation

Routes, previous/next, jump-to, kitāb/bāb browser, keyboard.

**Direction.** Arabic runs right to left, so moving forward through the book
moves *left* across the screen. Next sits on the left with a left arrow and
answers to `ArrowLeft`; previous sits on the right. Label every control with a
word as well as an arrow — an arrow alone is ambiguous to a reader who carries
both conventions.

**Grid track order follows the writing direction.** In RTL, track 1 is the
*rightmost*, so a two-column layout with the Arabic on the left declares the
narrow track first. Writing it the LTR way round gives the margin the wide track
and still looks plausible in a screenshot. Assert the side and the relative
width; do not eyeball it.

**Derive neighbours from the index, not from the loaded record.** The index is
in memory from boot, so controls render and the keyboard fires the instant a URL
is known. Reading them off the record means keypresses are silently dropped
during a fetch and the footer pops into existence when it arrives — a layout
shift on every navigation.

*Gate:* First → last → first by every mechanism. Deep links restore exact state.
Back/forward restore URL *and* content. No layout shift on navigation.

### Phase 6 — The reading pane

Each word its own element; selection; keyboard traversal; `?w=` deep links.

Wrapping words in spans is safe because Arabic shaping is word-internal —
letters join within a word, never across the space between two. Emit the
separator as a bare text node *between* the spans, not inside them.

**Paint the selection outside the box.** A spread `box-shadow` gives the
highlight breathing room with zero geometry change. Horizontal padding cancelled
by a negative margin nets to zero at integer sizes but not fractional ones —
0.15em is 3px at 20px text and 4.5px at 30px — and glyphs move.

Use a roving tabindex: one tab stop for the pane, arrows within it. Individual
tab stops would put 1,635 of them between the reader and the footer on the
longest hadith. The arrows are shared with hadith navigation; while a word is
focused they traverse words, and Escape hands them back.

*Gate:* Keyboard-only traversal reaches every clickable word and skips unbound
ones. Selection survives a reload via the deep link. No layout shift on
selection.

**[CORRECTED] On comparing against unsegmented text.** Revision 1 asked for a
bitmap comparison. That is the wrong instrument: each inline box rounds its own
advance width, so a line built from 39 spans distributes subpixels differently
from the same line as one text node and lights up ~1% of pixels while nothing
about the shaping has changed. Measure **line breaking and per-line ink extent**
instead. Correct output has 0px deviation at every size step.

### Phase 7 — The word panel

Eight sections, most-useful-first, provenance last and collapsed. A section with
nothing to say is not rendered — no empty boxes, no lonely labels. Where an
absence is *meaningful*, say why instead of showing a blank.

The curated literal/technical pair is the single most valuable thing on the
panel. Give it real weight. `overlap_score` drives visual weighting and is never
printed: `0.14` tells a student nothing.

`classical_sense_sample` is **one sampled definition** out of `lane_entry_count`
and is often not the sense the word carries. Under **ṣalāh** it reads *"the
middle of the back of a human being and of any quadruped."* Label it, size it
small, and caption it *not the definition of this word*.

Parse `gloss_msa` at build time. Finding the stem is not positional: in
`the + prayer;salat + [fem.sg.]` it is slot 1, in `and + I + leave;quit` it is
slot 2 because `I` is the imperfect subject prefix. Identify it by elimination
against a closed clitic set built from what actually occupies the proclitic slot.

Filter the classical keyword clusters **by kind, not frequency**. Lane's
editorial vocabulary is dense — `tropical` appears in 51% of entries, `became`
in 35%, `assumed` in 29% — but `camel` is in 15.5% and is a genuine sense.
Remove the apparatus and English function words; use frequency only to order
what survives.

*Gate:* Click through a sample spanning every `divergence` value, root present
and absent, a proper noun, a hapax, a curated term, a low-confidence binding and
an unbound token. No empty boxes, no raw Buckwalter, no untreated nulls.

### Phase 8 — Controls, design, polish

Size toggle (5 steps, Arabic only, persisted), diacritics toggle, bottom sheet
on narrow screens, loading/error/offline states, `prefers-reduced-motion`,
`prefers-color-scheme`.

**Choose the Arabic face by measurement, under a full harakat load.** Amiri
needs 1.90× its font size in vertical ink, Scheherazade New 1.80×, Noto Naskh
1.40×. Amiri is the most demanding and that is why it wins: this product teaches
vocalisation, so the marks are the content.

**Scale the leading inversely with the size.** The mark stack takes a fixed
proportion of the em, so a 20px line has ~2px of clearance and a 40px line ~7px.
Small text needs proportionally *more* leading. A constant line-height looks
fine in a specimen and crowds the harakat at the smallest step.

**Verify Latin diacritic coverage before choosing.** Transliteration needs ʿ
(U+02BF) and ʾ (U+02BE). Of five sans faces checked: IBM Plex Sans lacks twelve
of fifteen, Archivo six, Public Sans both hamza marks, Fira Sans ʾ. Only Inter
and Source Serif 4 are complete.

Resist the cream-paper-and-terracotta manuscript pastiche. The distinctive thing
about this product is not that the text is old but that it tells you how it
knows; design it as an instrument, not a relic.

*Gate:* Lighthouse accessibility ≥ 95. Keyboard-only walkthrough. Screenshots at
360/768/1440. Contrast checked including hover and selection against the Arabic,
in both colour schemes. Reduced motion verified.

**When measuring contrast, resolve colours through a canvas.** Design tokens
authored in `oklch` come back from `getComputedStyle` as `oklab()`/`lab()`;
parsing those channels as RGB reports near-black on near-white as 1.5:1. And a
decorative bar with no text is WCAG 1.4.11 non-text contrast — measure its fill
against what sits behind it, not its inherited text colour.

### Phase 9 — Generalisation

Extract every corpus-specific assumption into `corpora/{id}.yaml`. Namespace
build outputs per corpus. Document the workbook schema.

*Gate:* **A second corpus runs through the pipeline, or its failure is
documented with specificity.** A generalisation claim never tested against a
second input is not a generalisation claim. See the addendum.

### Phase 10 — Search

An inverted index over the same normalisation the lexicon joins on, so a student
can type without diacritics and match vocalised text. 18,578 keys, 94,404
postings, **150 KB brotli** — small enough to be one lazily-fetched file rather
than another shard set, and it has no business in the cold load.

Postings are record sequence numbers, delta-encoded ascending; the median key
has one posting and the commonest has 2,343.

Multiple terms are **best-match, not strict AND** — the records matching the
greatest number of distinct terms. Someone typing a half-remembered phrase
should get the closest hadith rather than nothing.

*Gate:* An undiacritised query finds diacritised text. Multi-term queries rank
sensibly. The empty state explains that search matches the form, not the root.
Accessibility unchanged.

---

## 7. Standing rules

- **Stop at every gate.** Report the numbers the gate asks for. Do not proceed
  on a failed gate by narrowing the criterion.
- **Never fabricate linguistic data.** If the lexicon has no root, the UI says
  there is no root. Do not infer, do not guess, do not let a language model
  invent one at runtime.
- **Preserve nulls end to end.** Every coercion of `null` to `""` destroys the
  distinction between "absent by design" and "missing".
- **Measure before optimising.** The corpus is 127k tokens. Most performance
  worry is misplaced.
- **When the data contradicts this document, trust the data and report the
  contradiction.** This revision exists because that rule was followed.
- **Check the instrument before believing the reading.** Three separate
  measurements in this build were wrong before the things they measured were: a
  contrast check reporting 1.5:1 for black on white, a shaping check flagging a
  1.1% pixel difference as failure when line geometry was identical, and an
  assertion failing on `Technical` vs `TECHNICAL` because `inner_text()` returns
  rendered text. A test that fails for the wrong reason is worse than no test.
- **Do not read exit codes through a pipe.** `cmd | tail` reports `tail`'s
  status, not `cmd`'s.

---

## 8. Working agreement

Decided deliberately; do not change it without saying why.

**Validation happens on pull requests, not on pushes to `main`.** The `test` job
in `.github/workflows/deploy.yml` is gated on `github.event_name ==
'pull_request'`, so a push to `main` builds and deploys without running the
gates. That is intentional: a red build should not stand between an author and a
deploy on a project with one maintainer.

The consequence has to be stated plainly, because it is easy to forget: **a
change pushed straight to `main` is never tested by CI.** If a change is worth
checking, open a pull request. The four end-to-end suites and the pipeline gates
run there, on the built artifact, in a clean Linux environment — which is not
the same thing as having been checked on the author's machine or in an
assistant's sandbox.

**Deliver changed files, not archives.** When handing work over, list the
destination path for every file and give the exact `git` command. A fix that
lands in the wrong directory, or a set of five files delivered as four, is
indistinguishable from a bug.

**Measurements are code.** Any figure quoted as evidence — an accuracy, a
coverage percentage, a byte budget — belongs in a committed test that fails when
it stops being true. A number produced by a throwaway script is an assertion,
not a measurement, and it decays silently.

**Where the work stands.** Every phase of this spec, of `REVIEW.md`, of
`ROADMAP.md` Stage 5 and of `ARCHITECTURE.md` is shipped or measured and
declined. The open work is [`MULTI-TEXT.md`](MULTI-TEXT.md): serving more than
one book. Start there, and start at Phase 1 rather than Phase 0 — the reason is
in that document.

**What a new conversation should read, in order.** `README.md` for the shape of
the repository; this file §8 for the working agreement; `LIMITATIONS.md` for
what the data is actually worth; `MULTI-TEXT.md` for what to build next. The
phase reports in `pipeline/reports/` are history, not instruction.

