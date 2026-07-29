# Phase 9 — generalisation & documentation

**Gate: a second corpus runs through the pipeline.** It does — after four defects
that only a second input could have exposed.

## The second corpus

`al-Rawḍ al-Miʿṭār fī khabar al-aqṭār`, al-Ḥimyarī's geographical dictionary
(OpenITI `0900AH`, 3.15 MB). Chosen to break things: a different genre from a
hadith collection, and carrying the `.mARkdown` extension al-Tajrīd lacks.

| | first run | after config fixes |
|---|--:|--:|
| Records | 86 | **3,255** |
| Tokens | 311,825 in 29 records | 311,825 across 3,255 |
| Residual markers | 56 records polluted | **none** |
| Warnings | 1,632 | 19 |

Final structure: 29 letter headings, 1,614 entry headings, 1,612 entry bodies.

## What broke

**1. The cache was single-corpus.** `fetch.py` wrote one `manifest.json` and
refused to mix corpora in it — safe, but it made a second text impossible
without deleting the first. It fired on the very first command. Now one manifest
per corpus.

**2. The section marker was assumed.** al-Tajrīd uses `### |`. This text tags
dictionary entries with an OpenITI *semantic* marker, `### $DIC_TOP$` — 1,613 of
them against 29 `### |` letter headings. The segmenter matched only the 29, ran
1,613 entries together into 29 records, and left `###` strings inside the text.
**Fixed in configuration alone**, which is the point: `segmentation.section`
became a regex matching either.

**3. A crash when a corpus has no numbered records.** The Phase 1 report picks a
shortest and longest hadith to print. A dictionary has no numbered records, so
`min()` raised on an empty sequence. Code fix: fall back to the body layer, then
to all records, and drop the zawāʾid sample when there are none.

**4. Build outputs collided.** Both corpora wrote `pipeline/build/records.json`,
so the second silently overwrote the first. Now namespaced per corpus.

One convention remains unhandled: 19 lines use `%~%` as a verse hemistich
separator outside a `#` prefix. Their text is still captured — the segmenter
warns and appends it — but they are counted as body prose rather than verse.
0.07% of lines, documented rather than fixed.

## What moved from code to configuration

`corpora/{id}.yaml` now carries the line grammar, marker strip list and its
order, page-marker patterns, opener syntax, aside bullet and marker, the
book-level heading prefixes, the editorial cross-reference pattern, layer names,
the workbook-index phantom rule, expected per-layer token tallies, and the
workbook sheet/column mapping. `segment.py` contains no Arabic string and no
corpus-specific regex.

Verified by regression: al-Tajrīd still produces 2,550 records and 127,161
tokens, −0.036% against the workbook, identical to Phase 1.

## Documentation

- `README.md` — run it, add a corpus, the workbook schema, reading the coverage
  report, deploying. Includes a table of how the two shipped corpora differ.
- `LIMITATIONS.md` — the workbook's three caveats plus the measured binding-tier
  error rates, and the two broken figures in the source workbook.
- `/about` in the app, linked from every page: the same content, with the
  measured Tier 3 (97.2%) and Tier 4 (69.9%) accuracies and the plain statement
  that roughly one word in 140 is a guess.

## Regression after the refactor

| gate | result |
|---|---|
| Phase 5 | 26/26 |
| Phase 6 | 20/20 |
| Phase 7 | 164/164 |
| Phase 8 | 31/31, Lighthouse accessibility 100 |
