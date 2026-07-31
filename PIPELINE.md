# The pipeline, file by file

What each program does, what it reads and writes, and when it runs. This is
the map a person opens BEFORE a source file; the files' own docstrings carry
the detail, this carries the shape. Kept honest by the fact that CI is the
same commands in the same order — if this document and `deploy.yml` disagree,
one of them is wrong and it is probably this one.

Two kinds of trigger exist:

- **Every build** — runs in CI on every push and pull request, and locally
  when you run the pipeline by hand.
- **On change, cached** — expensive stages whose output is cached in CI,
  keyed on their own inputs; they rerun only when those inputs change.
  Locally they rerun whenever you invoke them.

---

## The build chain, in running order

| # | file | one line | reads | writes | trigger / cache key |
|--:|---|---|---|---|---|
| 0 | `fetch.py` | download and checksum every external source; refuses to proceed on changed input | corpus configs `corpora/*.yaml` | `pipeline/cache/` + manifests | every build; downloads cached on the corpus configs |
| 0b | `lane.py` | ingest Lane's Lexicon (61 MB sqlite) into structured entries keyed by root | cached Lane db | `build/lane/entries.json` (72 MB) | on change, keyed on `lane.py` (~90 s) |
| 1 | `analyse.py` | run BOTH analyser stacks — CAMeL (calima-msa-r13) and qalsadi+arramooz — over every workbook form and witness reading; choose each root by vocalisation → majority → Lane, never by alphabet; merge the stacks with a recorded `rootBasis` | workbook, witness CSV, Lane roots, CAMeL db | `build/morphology/analyses.json` | on change, keyed on `analyse.py` + workbook (~5 min) |
| 2 | `segment.py` | OpenITI mARkdown → `records.json`; the line grammar lives in `corpora/{id}.yaml`, the code holds no Arabic | fetched source text | `build/{corpus}/records.json` | every build (~5 s) |
| 3 | `disambiguate.py` | context-level morphology over whole sentences via `farahidi`; licensed to override the workbook ONLY on the measured geminate→hollow class | records.json | `build/{corpus}/disambiguated.json` | on change, keyed on `disambiguate.py` + `segment.py` (~5 min). MUST run after segment and before build — ordering it after build once shipped a payload with no contextRoot at all |
| 4 | `lexicon.py` | extract the workbook into `lexicon.json` + indices | workbook | `build/{corpus}/lexicon.json` | every build (~1 min) |
| 5 | `bind.py` | bind every corpus token to a lexicon entry, tier by tier, witness-aligned where possible | records, lexicon, witness | `build/{corpus}/bindings.json` | every build (~30 s) |
| 6 | `build.py` | assemble the payload: trim entries, apply context overrides and corrections, fold hamza radicals, suppress garbage transliterations, filter empty Lane senses, shard to budget, assert no orphans and the 100 ms panel budget, stamp `buildCommit` | everything above | `web/public/data/` | every build (~1 min) |
| — | `codegen.py --check` | fail the build if the TypeScript contracts drifted from `contracts.py` | contracts.py | (check only; without `--check` it writes `contracts.ts`) | every build |

Then the app: `npm ci && npx tsc -b && npm run build` in `web/`, the SPA
404 fallback copy, and — on `main` only — deploy to Pages.

## The library modules (imported, never invoked)

| file | job | used by |
|---|---|---|
| `contracts.py` | the single source of truth for every data shape; `contracts.ts` is generated from it | everything |
| `normalise.py` | `normalise()` and `root_key()` — THE join keys between tokens, lexicon and roots | everything |
| `tokenise.py` | a token is a maximal run of Arabic letters+marks; round-trips the record text exactly | bind, build, tests |
| `morphology.py` | recover the stem of the 409 forms whose supplied analysis kept only a clitic | build |
| `gloss.py` | parse the workbook's Buckwalter gloss chains (`the + prayer;salat + [fem.sg.]`) so raw markup never reaches a reader | build, tests |

## Tools run by hand (never in CI)

| file | job | when |
|---|---|---|
| `gold.py sample` | draw the 300-token stratified hand-check sample; write `gold/{corpus}/sample.json` + the review workbook | after any change that alters shown values (tests force this: payload drift under a drawn sample fails CI until regenerated or re-scored) |
| `gold.py score` | read the filled review workbook → per-stratum accuracy with Wilson intervals → `reports/gold.md` | whenever verdicts exist or change |
| `bakeoff_camel.py` | score CAMeL against the arramooz chain on all forms, Lane-adjudicated; wrote the evidence (`reports/camel-bakeoff.md`) on which CAMeL was adopted | when evaluating a provider; keep for the next candidate |

## The browser gates (`web/`)

| file | asserts | trigger |
|---|---|---|
| `serve.py` | static server with SPA fallback and the base-path emulation of GitHub Pages (incl. the 301 on the slashless prefix) | serves the gates, locally and in CI |
| `e2e_sample.py` | derives phase 7's stratified word sample from the artifact under test, deterministically | before the gates, every `test` job |
| `e2e_phase5.py` | reader shell: routing, deep links, 404s, layout stability (26 checks) | every `test` job — blocking on PRs, reporting on pushes; deploy never waits on it |
| `e2e_phase6.py` | selection and keyboard: traversal reaches every clickable word (event-driven, not clock-driven), Escape semantics, deep-link restore (20) | same |
| `e2e_phase7.py` | the word panel walked over the sample: no raw markup, no null leaks, Lane rendering, divergence promises, provenance collapsed (114) | same |
| `e2e_phase8.py` | accessibility and responsive layout (31) | same |

## The test suite (`pipeline/tests/`)

Runs on every build, ~20 s, no browser. Split along two axes (see
`conftest.py`): by what must exist on disk (workbook / fetched / built), and
by scope — corpus-agnostic **invariants** always run; per-corpus **pins**
live in `fixtures/{corpus}.yaml` and skip, naming the missing key, on a
corpus that has not supplied them. `--corpus` selects the text under test.

Notable: `test_gold.py` binds hand verdicts to the build they describe;
`test_payload_hygiene.py` pins closed the defect classes a reader found
(mixed hamza spellings, garbage transliterations, empty Lane senses, masked
radicals); `test_analyse.py` pins the الخطاب/مصر/غدا root-selection fixes and
holds a catastrophe floor — not a conformity target — against the workbook.
