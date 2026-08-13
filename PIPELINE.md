# The pipeline, file by file

This page says what each program does, what it reads, what it writes, and when
it runs. Read it before you open a source file. The docstring in each file gives
the detail. This page gives the shape.

CI runs the same commands in the same order. If this page and `deploy.yml`
disagree, one of them is wrong. It is probably this page.

Written to ASD-STE100 Simplified Technical English. See `DOCS.md`.

Two triggers exist:

- **Every build.** The stage runs in CI on each push and each pull request. It
  also runs when you start the pipeline by hand.
- **On change, cached.** The stage is expensive. CI caches its output and keys
  the cache on the stage's own inputs. The stage runs again only when an input
  changes. On your machine it runs each time you call it.

---

## Build order

| # | File | What it does | Reads | Writes | Trigger |
|--:|---|---|---|---|---|
| 0 | `fetch.py` | Downloads each external source. Checksums it. Stops the build if an input changed. | `corpora/*.yaml` | `cache/{corpus}/` and a manifest | Every build. Cache key: the corpus configs. |
| 0b | `lane.py` | Reads Lane's Lexicon from a 61 MB SQLite file. Writes entries keyed by root. | Cached Lane database | `build/lane/entries.json` | On change. Key: `lane.py`. About 90 s. |
| 1 | `analyse.py` | Runs two analysers over every form: CAMeL, and qalsadi with arramooz. Chooses each root by vocalisation, then majority, then Lane. Never by alphabet. Records which basis it used. | Workbook, witness, Lane roots, CAMeL database | `build/morphology/analyses.json` | On change. Key: `analyse.py` and the workbook. About 5 min. |
| 1b | `glossary.py` | Lifts the workbook's lexicography into a corpus-independent store. Run once. | Workbook | `build/glossary/glossary.json` | By hand, after the workbook changes. |
| 2 | `segment.py` | Turns a source text into records. The line grammar is in `corpora/{id}.yaml`. This file holds no Arabic that names a book. | Fetched source | `build/{corpus}/records.json` | Every build. About 5 s. |
| 3 | `disambiguate.py` | Runs sentence-level morphology through `farahidi`. Overrides the workbook on one measured class only: geminate to hollow. | `records.json` | `build/{corpus}/disambiguated.json` | On change. Key: `disambiguate.py` and `segment.py`. About 5 min. |
| 4 | `lexicon.py` | Extracts a workbook into `lexicon.json` and its indices. Fails if the corpus declares no workbook. | Workbook | `build/{corpus}/lexicon.json` | Every build, for a corpus with a workbook. About 1 min. |
| 5 | `bind.py` | Binds each token to a lexicon entry, tier by tier. Transfers vowels from a witness where one exists. Derives `lexicon.json` for a corpus that has no workbook. | Records, lexicon, witness, glossary | `build/{corpus}/bindings.json` | Every build. About 30 s. |
| 6 | `build.py` | Assembles the payload. Trims entries, applies corrections, shards to a byte budget, and checks that no reference is broken. | Everything above | `web/public/data/corpora/{corpus}/` | Every build. About 1 min. |
| 7 | `share.py` | Merges the entries that corpora hold in common into one shared set. Run last. | Every built corpus | `web/public/data/lexicon/` | Every build, after the last corpus. |
| — | `codegen.py --check` | Fails the build if the TypeScript contracts no longer match `contracts.py`. | `contracts.py` | Nothing, with `--check`. Writes `contracts.ts` without it. | Every build. |
| — | `sunnah_numbers.py` | Derives the sunnah.com address maps for Bulūgh and the Shamāʾil from a pinned second scrape, verifies them against the witness at textual identity plus hand-confirmed anchors, and refuses to write on any failure. | Cached witnesses (`fetch.py` first) | `corpora/data/*_sunnah_links.json`, committed | Only when a witness or the pinned source changes. Not part of the build — the build reads the committed maps. |

**Run `share.py` last.** It deletes the private copy of each shared entry. A
corpus built after it puts its own copy back. The reader then loads a stale
entry.

Then build the app. In `web/`, run `npm ci`, then `npx tsc -b`, then
`npm run build`. Copy the SPA 404 fallback. On `main` only, deploy to Pages.

---

## Library modules

You import these files. You do not run them.

| File | What it holds | Used by |
|---|---|---|
| `contracts.py` | Every data shape. `contracts.ts` is generated from it. | Everything |
| `corpus.py` | Loads a corpus config. Resolves a source path. Refuses to answer with another corpus's file. | Every stage |
| `normalise.py` | `normalise()` and `root_key()`. These are the join keys. | Everything |
| `tokenise.py` | A token is a run of Arabic letters and marks. Round-trips the record text exactly. | bind, build, tests |
| `vocalisation.py` | Classifies a token's own vowelling. Transfers marks without a change to any letter. | bind |
| `tiers.py` | The tier table. States which evidence each tier needs. | bind |
| `workbook.py` | Reads al-Tajrīd's spreadsheet. The only file that knows what a sheet is. | lexicon, glossary, analyse |
| `morphology.py` | Recovers the stem of 409 forms whose analysis kept only a clitic. | build |
| `gloss.py` | Parses the workbook's Buckwalter gloss chains. Stops raw markup from reaching a reader. | build, tests |

---

## Tools you run by hand

CI never runs these.

| File | What it does | When to run it |
|---|---|---|
| `gold.py sample` | Draws a 300-token stratified sample for a hand check. | After a change that alters a shown value. The tests force this. A payload that drifts under a drawn sample fails CI. |
| `gold.py score` | Reads the filled review workbook. Writes accuracy per stratum with Wilson intervals. | When a verdict changes. |
| `bakeoff_camel.py` | Scores CAMeL against the arramooz chain. Lane adjudicates. | When you evaluate a new analyser. |

---

## Browser gates

| File | What it checks |
|---|---|
| `serve.py` | Serves the built site. Emulates the GitHub Pages base path and the SPA fallback. |
| `e2e_sample.py` | Draws the word sample for phase 7 from the artifact under test. Deterministic. |
| `e2e_phase5.py` | The reader shell: routing, deep links, 404 states, layout stability. |
| `e2e_phase6.py` | Selection and keyboard: traversal, Escape, deep-link restore. |
| `e2e_phase7.py` | The word panel across the sample: no raw markup, no null values, Lane rendering, provenance. |
| `e2e_phase8.py` | Accessibility and responsive layout. |

The gates block a pull request. They report on a push. The deploy does not wait
for them.

---

## Test suite

The suite is in `pipeline/tests/`. It runs on every build in about 20 s. It
needs no browser.

`conftest.py` splits the tests two ways:

1. **By what must exist on disk**: a workbook, a fetched source, or a build.
2. **By scope**: an invariant applies to every corpus and always runs. A pin
   applies to one corpus, lives in `fixtures/{corpus}.yaml`, and skips with the
   name of the missing key.

Use `--corpus` to choose the text under test.

Four suites are worth your attention:

- `test_corpus_isolation.py` — one corpus must never read another's files. A
  wrong config trips this suite first.
- `test_determinism.py` — the same input must give the same output. Retrieval
  once depended on hash order, and two runs of the same code gave different
  results.
- `test_vocalisation.py` — the reader may add marks. It may not change a letter.
- `test_payload_hygiene.py` — the defect classes a reader already found stay
  closed.
