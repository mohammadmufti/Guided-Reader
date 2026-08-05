# Multi-text: a phased plan

The reader serves one book. Everything below is about serving several, and about
making the second one cheap so the tenth is cheaper.

Companion to `ARCHITECTURE.md`, which established the shared lexicon. That work
made a lexical entry corpus-independent; this makes the *product* corpus-aware.
Read `SPEC.md` §8 first — the working agreement about validation and file
delivery applies throughout.

---

## Where the seams already are, and where they are not

Done, and worth knowing so it is not redone:

- **Identifiers are stable.** `match_id` is derived from the form, not from
  frequency, so the same word has the same id in every corpus.
- **The lexicon is corpus-independent.** `lex/surface-*` carries only properties
  of the word; `lex/stats-*` carries the per-corpus counts. Asserted by
  `test_store_split.py`.
- **Lane and the classical apparatus are already shared**, keyed by root.
- **Segmentation is configuration.** `pipeline/corpora/{id}.yaml` holds the line
  grammar; `segment.py` contains no Arabic string. Proven on a second corpus.
- **`index.json` carries `corpus.id`.** The payload knows which text it is.

Not done, and each is a phase below:

- The payload lives at **one** path, `web/public/data/`, with no room for a
  second text beside it.
- The client has **no concept of a current corpus** — `data.ts` hard-codes the
  single path.
- ~~Routes are `/hadith/:number`.~~ DONE: routes are `/:corpus/read/:number`,
  with `/hadith/:number` redirecting to al-Tajrīd so existing links survive.
  The original note, still worth keeping: a geographical
  dictionary has entries, not numbered hadith.
- ~~CI builds one corpus.~~ DONE: CI builds al-Tajrīd and the Muwaṭṭaʾ end to
  end and segments al-Rawḍ, then runs `share.py` to deduplicate the lexicon.
- `rawd` stops at segmentation and has never produced a payload.

---

## Phase 0 — Choose a book

The reader must serve more than one text before anything else is worth doing.

### 0.1 Re-partition the payload

```
web/public/data/
  corpora.json                  the registry — what this deployment serves
  lexicon/
    surface-NNN.json            shared: properties of the word
    classical-NNN.json          shared: keyed by lane_root
    lane-NNN.json               shared: Lane entries by root
  corpora/{id}/
    index.json                  navigation, tree, counts, shards, buildId
    records/{recordId}.json     renamed from hadith/ — see 0.3
    stats-NNN.json              per-corpus counts
    search.json                 per-corpus, form and root postings
```

`corpora.json` is small and is the only file fetched before a corpus is chosen:

```json
{ "schemaVersion": 5,
  "corpora": [
    { "id": "tajrid", "titleAr": "…", "titleEn": "…", "author": "…",
      "unit": "hadith", "records": 2550, "displayNumbers": true,
      "hasGlosses": true, "hasWitness": true }
  ] }
```

`unit`, `displayNumbers`, `hasGlosses` and `hasWitness` are what let the
interface adapt without knowing which book it is holding — see 0.3 and Phase 2.

**Gate:** the Tajrīd payload is byte-identical in content, only relocated. Every
existing test passes. Cold load unchanged.

### 0.2 Corpus-aware client

- `data.ts` takes a corpus id and builds `${BASE}/data/corpora/${id}/…`; lexicon
  fetches go to `${BASE}/data/lexicon/…` and are **not** re-fetched when the
  corpus changes.
- Routes gain a corpus segment: `/:corpus/read/:record`.
- **Old links must keep working.** `/hadith/1` redirects to
  `/tajrid/read/matn-00004` (or its display number). Every link handed out so
  far has that shape; breaking them is not acceptable and a redirect is three
  lines.
- The corpus lives in the URL, not in a store, so a link carries it.

**Gate:** a deep link into either corpus restores exactly. `/hadith/1` still
lands on hadith 1. Switching corpus does not refetch a lexicon shard already in
memory — assert it, since that saving is the whole point of the split.

### 0.3 The record noun is corpus-specific

`/hadith/:number` assumes numbered hadith. Al-Rawḍ has 1,613 dictionary entries
with no numbers at all.

Route on the **record id**, which every corpus has: `/:corpus/read/:recordId`.
Where `displayNumbers` is true, also accept a number and resolve it — that keeps
`اذهب` and the jump control working for Tajrīd and simply hides them elsewhere.

`unit` supplies the word the interface uses: *hadith*, *entry*, *chapter*. It is
a label, not logic.

**Gate:** both corpora navigate first → last → first by every mechanism. The
jump control is absent, not broken, where numbers do not exist.

### 0.4 The picker

A control in the header listing what `corpora.json` advertises: title, author,
record count, and honestly what the text has — *no glosses*, *unvocalised* —
because Phase 2 will produce corpora that lack both.

**Gate:** Lighthouse accessibility stays at 100. Keyboard reachable. The current
corpus is announced, not merely styled.

---

## Phase 1 — A second corpus, all the way through

The architecture claims a text needs a config, a URI and a witness. **No corpus
has ever gone past segmentation.** Phase 9 of the original build found four
defects the moment a second text was tried, all invisible from reading the code.
That risk is unchanged and it gets more expensive the longer it waits.

Run `rawd` through `lexicon → bind → build`. Expect failures; they are the point.
Known in advance:

- `lexicon.py` requires a workbook. Al-Rawḍ has none, so it must degrade rather
  than fail — Phase 2.
- `bind.py` requires a witness. Al-Rawḍ has no parent text, so every token will
  land in Tier 5. That is the correct answer and the interface must survive it.
- `build.py` assumes `numberIndex` is populated.

**Gate:** `rawd` produces a payload and is readable. Every defect found is fixed
in the shared code, not worked around in a config.

---

## Phase 2 — Corpora without a workbook or a witness

What a text gets when it has neither:

| | with both | witness only | neither |
|---|---|---|---|
| Segmented, navigable, searchable | ✓ | ✓ | ✓ |
| Root, lemma, POS | ✓ | ✓ | ✓ (analysers) |
| Lane by root | ✓ | ✓ | ✓ |
| Vowelling | ✓ | ✓ | ✗ |
| MSA gloss | ✓ | ✗ | ✗ |

Note the middle column: the workbook is the **only** gloss source in the project
and no free Buckwalter/AraMorph package exists on PyPI. A new text gets no
glosses until one is found. That must be stated in the interface, not hidden by
an empty section.

Note also that **neither source text carries any harakāt** — al-Tajrīd's
mARkdown has zero diacritics across 1.4 million Arabic letters. All vowelling
comes from the witness. A corpus with no parent text is unvocalised, and the
harakāt toggle should be absent rather than inert.

**Gate:** a corpus with neither produces a working reader that says, in the
panel and on `/about`, exactly what it does not have.

---

## Phase 3 — Witnesses as configuration

Generalise the Bukhārī alignment. `corpora/{id}.yaml` gains:

```yaml
witness:
  uri: …
  numbering: content      # `content` retrieves by content; `row` means row N is record N
  min_coverage: 0.35
```

`content` is the default because it is what the data forced: the Bukhārī CSV has
7,008 rows against references running to 7,563, and every offset from −2 to +2
gives a flat ~24% overlap with no peak.

A commentary or a second abridgement of Bukhārī can then reuse the same witness
— which is the case worth optimising for, because those are the texts most
likely to be added next.

**Gate:** a third corpus sharing the Bukhārī witness reaches Tier 1+2 ≥ 90%
without a line of new code.

---

## Phase 4 — Things only a multi-text reader can do

Cheap once Phases 0–3 land, and pointless before:

- **Occurrences across texts.** The panel says "7 times here"; it could say "7
  here, 1,240 across the collection". The data is already factored for it.
- **Search across corpora**, with results grouped by text.
- **A word's history.** The same lexical entry seen in a 3rd-century ḥadīth
  collection and a 9th-century geography is a different kind of evidence from
  either alone.

**Gate:** none of these may slow the single-corpus cold load, currently 30 KB.

---

## Order, and what to do first

```
0.1 ─> 0.2 ─> 0.3 ─> 0.4 ─> 1 ─> 2 ─> 3 ─> 4
```

Strictly sequential, unusually for this project, because each phase is the
substrate of the next.

**If only one thing gets done, do Phase 1** — not Phase 0. Running `rawd` to a
payload on the *current* single-corpus layout is ugly but it surfaces the defects
now, when they are cheap, rather than after the re-partition when a failure could
be either the corpus or the new layout. Phase 0 is the better architecture;
Phase 1 is the better next hour.

## Standing constraints

- **Old links keep working.** `/hadith/1` has been handed out.
- **Every figure quoted is a committed test.** 61 exist; a new corpus adds its
  own rather than loosening theirs.
- **Absence is stated, never blank.** A corpus without glosses says so.
- **Validation on pull requests** — see `SPEC.md` §8. A push to `main` runs the
  pipeline tests but no browser gates.
- **The licence is GPL-3.0-or-later.** New dependencies must be compatible, and
  `NOTICE.md` gains an entry for each.
