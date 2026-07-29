# Addendum — adding a new data source

Companion to `SPEC.md`. That document describes building the pipeline; this one
describes feeding it something new.

Two kinds of addition are covered, and they are very different jobs:

- **A. A new corpus** — another text to read. Mostly configuration.
- **B. A new lexicon workbook** — the linguistic apparatus for that text. This
  is the hard one, and most of the work is verification.

Everything below was learned by actually doing it. The second corpus in this
repo, `al-Rawḍ al-Miʿṭār`, exposed four defects that no amount of reading the
code would have found.

---

## A. Adding a corpus

### A.0 One-time setup, done once for the whole platform

Lane's Lexicon is a shared lexical source, not a per-corpus one. Ingest it once
and never again:

```bash
python pipeline/fetch.py --corpus lane     # 61 MB, checksummed
python pipeline/lane.py                    # all 5,078 roots, 47,919 entries
```

`build.py` ships only the roots each corpus actually uses, so a new text with
unfamiliar roots needs no Lane re-run — the entries are already there. Do NOT
pass `--roots` unless you are deliberately building a cut-down set; doing so
couples the shared source to one corpus's vocabulary, which is the coupling this
arrangement exists to remove.

### A.1 The short version

```bash
cp pipeline/corpora/rawd.yaml pipeline/corpora/mytext.yaml
# edit: id, display, sources.text.uri, segmentation

python pipeline/fetch.py   --corpus mytext   # acquire + checksum
python pipeline/segment.py --corpus mytext   # -> records.json   [READ THE REPORT]
python pipeline/lexicon.py --corpus mytext   # workbook -> lexicon.json   (needs a workbook)
python pipeline/bind.py    --corpus mytext   # every token -> a lexicon entry
python pipeline/build.py   --corpus mytext   # -> web/public/data/
```

Intermediates land in `pipeline/build/mytext/`. **Stop after `segment.py` and
read its report before running anything else** — if residual markers are not
zero, everything downstream is built on garbage.

Steps 3–5 require a lexicon workbook. Without one you still get segmented,
navigable, searchable text; you do not get the word panel. See part B.

### A.2 Survey the text before writing any config

Do not guess the line grammar. Fetch the file and count:

```python
import re, collections
body = raw.split("#META#Header#End#", 1)[1]
pref = collections.Counter()
for line in body.split("\n"):
    if not line.strip():
        continue
    m = re.match(r'^(#+\s*\$[A-Z_]+\$|#+\s*\|+|~~|%~%|#\s|#)', line)
    pref[m.group(1).strip() if m else "<other>"] += 1
print(pref.most_common(12))
```

This single command is what turned a mystifying result into a five-minute fix on
the second corpus. It tells you, in order of importance:

1. **Which section marker the text uses.** al-Tajrīd uses `### |`. al-Rawḍ tags
   dictionary entries with an OpenITI *semantic* marker, `### $DIC_TOP$` — 1,613
   of them against 29 `### |` letter headings. Configured with the wrong pattern
   the segmenter matched only the 29, ran every entry together into 29 records,
   and left `###` strings inside the text. **Fixed in configuration alone**,
   which is the whole point of the exercise.
2. **How many structural levels there are.** If `### ||` appears, the hierarchy
   is encoded and you should read it rather than infer it. Neither text here has
   it, which is why both need a lexical heading rule.
3. **What editorial noise is present.** Both texts carry `PageV..P..`, `ms###`
   and Shamela `<div>` tags. al-Rawḍ additionally uses `%~%` as a verse
   hemistich separator, which al-Tajrīd never does.
4. **What is left over.** The `<other>` bucket is your list of unhandled
   conventions. Aim to drive it to near zero; document what remains.

### A.3 The configuration blocks

```yaml
id: mytext
display: { titleAr, titleEn, author, authorDied, edition, rights }
sources:
  text: { kind: http, uri, filename, encoding }
segmentation:
  section:        '^###\s*(?:\|+|\$DIC_TOP\$)\s*(.*)$'
  paragraph:      '^#\s(.*)$'
  continuation:   '^~~(.*)$'
  strip:                       # ORDER MATTERS — see A.4
    - { name: manuscript_marker, pattern: '\bms\d+\b' }
    - { name: page_volume,       pattern: 'PageV\d+P\d+' }
    - { name: shamela_div,       pattern: '<div[^>]*>' }
  page_marker_alt: 'PageV(\d+)P(\d+)'
  page_marker:     '\[\s*ص\s*:\s*(\d+)\s*\]'
  opener:          '^(\d+)\s*-\s*(.*)$'
  aside_bullet:    '^•\s*(.*)$'          # omit if the text has no asides
  aside_marker:    'زوائد الضياء'
  heading_top_prefixes: ["كتاب", "أبواب"]
  editorial_reference: '\(\s*بخاري\s*:\s*([\d\s،,و–-]+?)\s*\)'
  layer_names: { body: matn, aside: zawaid, top: heading_kitab,
                 sub: heading_bab, front: frontmatter }
  workbook_index_phantoms: false
expected:
  layer_tokens: { … }          # omit if there is no workbook to compare against
lexicon:
  workbook: MyText_frequency_tables.xlsx
  sheets: { … }
```

`segment.py` contains no Arabic string and no corpus-specific regex. If you find
yourself wanting to edit it to add a text, that is a bug in the configuration
surface — report it rather than working around it.

### A.4 Four things that will bite

**Strip order matters.** Manuscript markers occur *inside* both the div tags and
the page brackets, so whichever marker can nest must be stripped first. The yaml
lists them in application order; do not reorder it casually.

**Openers may carry more than one number.** `### | 1201 - 1202 - ` is one record
covering two hadith. The parser chains leading `N -` groups and the record keeps
every number it covers, so nothing looks like a gap that isn't one.

**A corpus need not have numbered records at all.** A geographical dictionary has
none. Anything that picks a "shortest" or "longest" numbered record must fall
back — this crashed with `min() arg is an empty sequence` on the second corpus.

**Namespace everything per corpus.** The cache manifest, the build directory,
and the reports. A single shared manifest makes a second corpus impossible
without deleting the first; a shared build directory means the second silently
overwrites the first.

### A.5 What "it worked" looks like

From the second corpus, before and after fixing the section pattern:

| | first run | after config fix |
|---|--:|--:|
| Records | 86 | 3,255 |
| Tokens | 311,825 in 29 records | 311,825 across 3,255 |
| Residual markers | 56 records polluted | none |
| Warnings | 1,632 | 19 |

**Residual markers must be zero.** That assertion is the single most useful
signal that a config is right: if `###` or `~~` survives into a record, your
section or continuation pattern is wrong and everything downstream is garbage.

**Warnings should be a rounding error.** 19 of 28,313 lines (0.07%) is
acceptable and documented — they are `%~%` verse lines whose text is still
captured but counted as prose. 1,632 was a signal, not noise.

---

## B. Adding a lexicon workbook

A corpus without a workbook still reads: you get segmented, navigable text with
no annotation. To light up the word panel you need a frequency workbook, and
this is where the real risk lives, because a *plausible but wrong* workbook
produces a reader that confidently teaches incorrect vowelling.

### B.1 Required schema

**`Surface`** — one row per vocalised surface form. The primary key is
`match_id`, formed `{search_key}#{n}` with `n` ranking homographs by descending
frequency. Required columns:

```
match_id  search_key  vocalized  unvocalized  freq  rank  pct  cum_pct
doc_freq  pos  lemma  root  gloss_msa  layers  first_record  divergence
```

Optional but used if present: `din_31635`, `lemma_din`, `lane_root`,
`classical_keywords`, `classical_sense_sample`, `classical_senses_more`,
`lane_entry_count`, `literal_sense`, `technical_sense`, `domain`,
`overlap_score`, `voc_source`, `morph_confidence`, `pos_agreement`, `kwic`.

**`Lemma`** keyed by `lemma`; **`Root`** by `root`; **`Names`** by `name`;
**`TechnicalSenses`** by `key` (a search key, not a vocalised form);
**`Divergence`** by `lemma`; **`Unvocalized`** by `unvocalized`; **`Review`** by
`surface` — **which is the undiacritised form, not the search key.**

### B.2 Verify in this order, and stop at the first failure

**1. The join key.** `normalise(vocalized)` must equal `search_key` for every
row. `lexicon.py` asserts this and refuses to emit anything until it passes. If
your workbook normalises differently, change `normalise.py` — and remember that
`codegen.py` regenerates the TypeScript twin, so the app and the pipeline cannot
drift apart.

Derive the rules from character-frequency arithmetic rather than from a
description. Compare the character inventory of `vocalized` against
`search_key`; the deltas fix every rule with no guesswork. The trap: the hamza
fold is not uniform — alef-seated hamza goes to bare alef, waw- and yeh-seated
hamza go to bare hamza. Getting that backwards mis-joins ~600 forms and still
looks plausible.

**2. Referential integrity.** Every `Surface.lemma` must exist in `Lemma`, every
`Surface.root` in `Root`. In the shipped workbook these are clean;
`TechnicalSenses` has two roots absent from `Root`, which is harmless and worth
noting rather than fixing.

**3. The tokenisation.** Reconstruct the workbook's own token count from your
segmented records and compare per layer. If you are more than a couple of
percent out, you have not found their tokenisation. Ours strips the editorial
cross-reference and counts only tokens containing an Arabic letter; a naive
whitespace split overshoots by 12.6%.

**4. The headline figures.** Recompute every coverage percentage and type count
the workbook claims. Deviation means your extraction is wrong — or the
workbook's summary is, which happened twice in the shipped one. Both are worth
knowing; do not silently accept either.

### B.3 A vocalisation reference

Tier 2 binding needs a fully diacritised edition of the same or an overlapping
text. Requirements:

- Same orthographic conventions, or the exact-string match to `vocalized` will
  fail. In the shipped pair, 92.8% of reference tokens match a `vocalized` value
  exactly, which is what makes the transfer work.
- **Do not assume it is indexed by anything.** The shipped Bukhārī CSV is not
  indexed by hadith number: 7,008 rows against cross-references running to
  7,563, and every offset from −2 to +2 gives a flat ~24% overlap with no peak.
  Retrieve the counterpart by content — an IDF-weighted inverted index over rare
  tokens gets a median overlap of 0.959.

Check the licence. The shipped reference has none, so it is used to transfer
vowelling and no text from it is redistributed.

### B.4 If binding falls below the gate

`bind.py` prints the tier table. If Tier 1+2 is under 90% on matn:

- Check the retrieval coverage line beneath it. A median below ~0.9 means the
  reference is not matching — different edition, different orthography, or a
  genuinely different text.
- Check Tier 1 alone. It should land near the proportion of unambiguous keys
  (50.3% here); much lower means the join key is wrong, which sends you back to
  B.2 step 1.
- Do not compensate by loosening Tier 2's acceptance. Coverage bought by
  accepting bad alignments is worse than honest low coverage, because the
  interface will present it as `high` confidence.

### B.5 Update `LIMITATIONS.md`

Non-negotiable. The measured Tier 3 and Tier 4 accuracies are corpus-specific
and are the numbers a student is actually trusting. Re-run the held-out
evaluation, put the new figures in the file and in the app's `/about` page, and
restate the "roughly one word in N is a guess" sentence with the correct N.

A reader has no way to tell a witnessed reading from a guess unless the
interface tells them. That is the whole contract.

---

## C. Checklist

```
[ ] Surveyed the line grammar; <other> bucket near zero
[ ] segmentation config written; no edits to segment.py
[ ] fetch --corpus X          checksums, idempotent, own manifest
[ ] segment --corpus X        residual markers: NONE
[ ] warnings a rounding error, remainder documented
[ ] normalise() reproduces search_key on 100% of rows
[ ] referential integrity clean or deviations recorded
[ ] token counts within 2% per layer, or tokenisation understood
[ ] every headline coverage figure recomputed and reconciled
[ ] vocalisation reference: orthography matches, licence checked
[ ] Tier 1+2 >= 90% of body tokens
[ ] held-out Tier 3 / Tier 4 accuracies measured
[ ] Lane ingested once, whole (python pipeline/lane.py, no --roots)
[ ] build.py ships only this corpus's roots — payload size sanity-checked
[ ] LIMITATIONS.md and /about updated with the new figures
[ ] all e2e gates re-run green
```

## D. What is NOT automated

Being explicit, because "configuration-driven" can be read as more than it is:

- **Surveying the line grammar is manual.** A.2 gives you the command; reading
  its output and deciding what the markers mean is a judgement call.
- **The heading-level rule is a judgement call.** `heading_top_prefixes` worked
  for both shipped corpora, but a text whose structure is encoded differently
  will need thought, not a config tweak.
- **There is no automatic morphological analysis.** A form absent from the
  lexicon binds at Tier 5 and is inert. Roadmap B.3 addresses this; until then,
  a text without a matching workbook is a reading surface, not an annotated one.
- **The preview artifact is a separate hand-maintained implementation.** See the
  note in ROADMAP under E.4.
