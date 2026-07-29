# Tajrīd Reader

A word-by-word reading surface for **al-Tajrīd al-Ṣarīḥ li-aḥādīth al-Jāmiʿ
al-Ṣaḥīḥ**, al-Zabīdī's abridgement of Ṣaḥīḥ al-Bukhārī. One hadith on screen;
click any word to see its vowelling, root, lemma, modern gloss, and — where the
classical and modern senses have parted company — the gap between them.

It is built for a student who can read Arabic but cannot yet read *this*.

**Read [LIMITATIONS.md](LIMITATIONS.md) before trusting the vowelling.**
About one word in 140 is a guess. The app says which ones.

- [`SPEC.md`](SPEC.md) — the build spec, corrected against the measured data
- [`ADDENDUM-adding-sources.md`](ADDENDUM-adding-sources.md) — adding a corpus
  or a lexicon workbook
- [`ROADMAP.md`](ROADMAP.md) — what is not built yet, and why in that order
- [`DEPLOY.md`](DEPLOY.md) — CI, hosting, and seeing changes live

---

## Run it

```bash
# 1. Fetch sources (idempotent; refuses to proceed on changed input)
python pipeline/fetch.py

# 2. Build the data
python pipeline/segment.py      # mARkdown  -> records.json
python pipeline/lexicon.py      # workbook  -> lexicon.json
python pipeline/bind.py         # every token -> a lexicon entry
python pipeline/build.py        # -> web/public/data/

# 3. Run the app
cd web && npm install && npm run dev
```

Requires Python 3.12 with `pandas`, `openpyxl`, `pyyaml`, `brotli`; Node 22.

The end-to-end tests need `playwright` and a Chromium build:

```bash
cd web && python e2e_phase5.py && python e2e_phase6.py \
                && python e2e_phase7.py && python e2e_phase8.py
```

---

## Adding another corpus

Every corpus-specific assumption lives in `pipeline/corpora/{id}.yaml` — source
URI, line grammar, marker patterns, opener syntax, heading rules, layer names,
and the lexicon workbook mapping. Nothing about a particular text is in the code.

```bash
cp pipeline/corpora/rawd.yaml pipeline/corpora/mytext.yaml
# edit it, then:
python pipeline/fetch.py   --corpus mytext
python pipeline/segment.py --corpus mytext
```

Outputs are namespaced: `pipeline/build/{corpus}/`.

### The line grammar

OpenITI texts do not agree with each other. The two shipped configs differ in
ways worth knowing before you write a third:

| | al-Tajrīd | al-Rawḍ al-Miʿṭār |
|---|---|---|
| Section marker | `### \|` | `### $DIC_TOP$` (semantic tag) |
| Structural levels | one only — no `### \|\|` | one |
| Body lines | `# ` + `~~` continuations | same |
| Editorial noise | `PageV..P..`, `ms###`, Shamela `<div>` | same, plus `%~%` verse separator |
| Numbered openers | yes, `N - ` | none |

Set `segmentation.section` to whatever that text uses. If a corpus has no
workbook, omit the `expected` and `lexicon` blocks; the segmenter reports token
counts without comparing them to anything.

### The lexicon workbook schema

A different text needs a frequency workbook with the same shape. Required:

- **Surface** — one row per vocalised surface form, keyed by `match_id`
  (`{search_key}#{n}`, n ranking homographs by descending frequency). Must carry
  `search_key`, `vocalized`, `unvocalized`, `freq`, `rank`, `pct`, `cum_pct`,
  `doc_freq`, `pos`, `lemma`, `root`, `gloss_msa`, `layers`, `first_record`,
  `divergence`.
- **Lemma**, **Root**, **Names**, **TechnicalSenses**, **Divergence**,
  **Review**, **Unvocalized** — keyed as listed in the yaml.

`search_key` must be reproducible from `vocalized` by `pipeline/normalise.py`,
and `lexicon.py` asserts that on every row before it will emit anything. If your
workbook normalises differently, change `normalise.py` and the assertion will
tell you when it agrees.

---

## Reading the coverage report

`python pipeline/bind.py` prints the tier table. The number that matters:

```
GATE — Tier 1+2 on matn: 97.0%   (requires >= 90.0%)
Naive ceiling for comparison: 85.9%
```

Tiers 1 and 2 are witnessed readings. Tier 3 is inference, Tier 4 a guess. If
Tier 1+2 falls below 90% on a new corpus, the vocalisation reference is probably
not aligning — check the retrieval coverage line beneath it, which should show a
median above 0.9.

`python pipeline/lexicon.py` verifies every coverage figure against the values
recorded in the spec and fails loudly if extraction has drifted.

---

## Deploying

`web/public/data/` is static and immutable. `npm run build` emits `web/dist/`;
serve it from any static host. `web/public/_headers` sets the cache policy —
`index.json` revalidates, everything else is `immutable` because the client
requests it with `?v={buildId}`.

Cold load is 27 KB brotli worst case, including the index. Precompressed `.br`
and `.gz` siblings are written for every file; configure the host to serve them.

---

## Layout

```
pipeline/
  corpora/{id}.yaml   every corpus-specific assumption
  fetch.py            checksummed, idempotent source acquisition
  segment.py          mARkdown -> records, config-driven
  normalise.py        the join key, asserted against 22,464 rows
  lexicon.py          workbook -> lexicon.json + indices
  gloss.py            Buckwalter glosses -> renderable structure
  bind.py             five-tier token binding
  build.py            -> web/public/data/, sharded and compressed
  contracts.py        SINGLE SOURCE OF TRUTH for the data contracts
  codegen.py          emits web/src/types/contracts.ts; --check fails on drift
web/
  src/components/     ReadingPane, WordPanel, controls, browser
  e2e_phase*.py       the gate checks, run against a real browser
```

Do not hand-edit `web/src/types/contracts.ts`. Edit `contracts.py` and run
`python pipeline/codegen.py`.
