# Architecture: a shared lexicon, per-corpus alignment

Addendum to `SPEC.md`. Settles how word identification should be organised once
there is more than one text. Supersedes the workbook-as-foundation model.

Every claim here was checked against the tools and the data; where something was
tried and did not work, it says so.

---

## 1. The shape

Four problems, four sources, and only one of them is corpus-specific.

```
                          CORPUS-INDEPENDENT                 PER CORPUS
                          (built once, grows)                (built per text)

form inventory      ┌──────────────────────────┐      ┌─────────────────────┐
  + lemma/root/pos  │  lexicon/                │      │  corpora/{id}/      │
  + gloss           │    forms/{shard}.json    │◀─────│    records.json     │
  + classical       │    classical/{shard}.json│      │    bindings.json    │
                    └──────────────────────────┘      │    stats/{shard}    │
                             ▲                        │    search.json      │
                             │ contributes            └─────────────────────┘
                    ┌────────┴─────────┐                       ▲
                    │  providers       │                       │ vowelling
                    │  · witness       │              ┌────────┴────────┐
                    │  · qalsadi       │              │  aligner        │
                    │  · workbook      │              │  vs that text's │
                    │  · Lane          │              │  own witness    │
                    └──────────────────┘              └─────────────────┘
```

The lexicon answers *what forms exist and what they mean*. The aligner answers
*which reading is right here*. Nothing should ask the lexicon to decide a vowel,
and nothing should ask the aligner for a root.

## 2. Where the form inventory comes from, without a workbook

This is the question that had no answer before, and it turns out to have a good
one.

`qalsadi` returns a single `(lemma, pos)` per form — not a candidate set. So it
cannot generate a form inventory on its own. But it does not need to:

**The vocalised witness generates the inventory; the analyser annotates it.**

A fully-diacritised edition of the parent text is a list of real vocalised forms
in real contexts. Running the normalisation over it gives, for free, a map from
each undiacritised spelling to every vocalisation actually attested for it —
which is precisely the candidate set binding needs. `qalsadi` then supplies
lemma, root and POS per vocalised form.

That means **a new text needs a vocalised witness, not a bespoke workbook.** The
witness is the same artifact the aligner already requires, so the cost is zero.

Verified against the Bukhārī witness we already hold: 92.8% of its tokens match a
`vocalized` value the workbook contains, so a witness-derived inventory would
cover the same ground and then some — it is not bounded by what one corpus
happened to use.

## 3. Providers, and field-level provenance

The lexicon is **merged from providers, with provenance per field**, not sourced
from one place. That is what lets a bad value be overridden without discarding
the good ones beside it.

| provider | contributes | quality |
|---|---|---|
| **witness** | vocalised forms, attestation counts | ground truth for *what exists* |
| **qalsadi** | lemma, root, pos | good; known hollow-verb weakness |
| **workbook** | `gloss_msa`, curated literal/technical pairs, Names, divergence | the ONLY gloss source available |
| **Lane** | classical apparatus by root | complete, 5,078 roots |
| **corrections** | anything | human, wins over everything |

Precedence, highest first: **corrections → witness → qalsadi → workbook**.

The workbook stays, but demoted from foundation to contributor. Two reasons it
cannot be dropped:

- **No installable Buckwalter/AraMorph.** `aramorph` is not on PyPI. The
  workbook's `gloss_msa` (21,028 forms, 98.2% token coverage) is the only source
  of English glosses in the project. A new corpus without a workbook gets
  lemma, root, POS, vowelling and Lane — but no MSA gloss until a source is found.
  That gap should be stated in the interface, not hidden.
- **86 curated technical senses and 333 names** are hand work no tool reproduces.

Every shipped field carries `source`. The panel already renders provenance for
vowelling; this extends the same discipline to morphology.

## 4. Why qalsadi is not a new dependency

The workbook's own README: *"Morphology — qalsadi (lemma, root) reconciled
against the Buckwalter/AraMorph analyser (POS, English gloss)."*

It is already qalsadi output, cached, filtered through one corpus, and lossy.
Run directly it recovers what the cache dropped:

| form | workbook | qalsadi |
|---|---|---|
| `وَلْيُحَدِّثْ` | particle, lemma `لِ`, no root | **حدث, verb** |
| `سَيَفْقِدُونَنِي` | particle, lemma `سَ`, no root | **فقد, verb** |
| `فَلْيُبَايِعْنِي` | particle, no root | **بايع, verb** |
| `لِتَكُونَ` | root `كوي` | `كوي` — genuine limitation, inherited |

`سَيَفْقِدُونَنِي` is one of the 263 forms previously called unrecoverable.

## 5. The aligner, per corpus

93.8% of matn tokens already sit inside a Bukhārī matching block. The headroom is
not more witnesses:

| | tokens | share | remedy |
|---|--:|--:|---|
| matched | 117,373 | 93.8% | — |
| aligned record, unmatched token | 7,665 | **6.1%** | **better aligner** |
| record never aligned | 149 | 0.1% | another witness |

**Measured, and the headroom is much smaller than this table suggests.** Of the
7,665 unmatched tokens, only **1,670 (21.8%)** have their word present in the
witness row at all; the other **5,995 (78.2%)** are genuinely absent — the
abridger's own wording, or a different recension. No aligner recovers those.

And a gap-filling pass over the 1,670 produced **zero** matches, for a structural
reason: `difflib` returns maximal blocks under a longest common subsequence, so
a word unique in both gaps is already matched. The residue is REORDERING, and
matching a reordering means allowing crossing alignments — which gives up the
positional determinacy that makes Tier 2 high confidence in the first place.

**Recommendation: do not do D-1.** The realistic ceiling is 1.3% of the corpus,
it cannot be reached without weakening the guarantee that makes the tier
meaningful, and B-3 delivered three times as much by widening the inventory
instead. What follows is kept for the record.

Were it attempted anyway:

1. **Anchor on rare words.** Match low-document-frequency tokens first; they are
   nearly unambiguous and they partition the sequence.
2. **Align between anchors** with Needleman–Wunsch over a substitution cost that
   is cheap when two forms share a consonantal skeleton and expensive otherwise —
   the information normalisation throws away is exactly what scores a substitution.
3. **Accept a match only when positionally determined**, as now.

Every token this recovers arrives at the *highest* confidence tier, witnessed
rather than inferred. That is the argument for doing it before anything
statistical.

Configuration per corpus, in `corpora/{id}.yaml`:

```yaml
witness:
  uri: …                    # a fully-diacritised edition of the parent text
  numbering: content        # `content` = retrieve by content; `row` = row N is hadith N
  min_coverage: 0.35
```

`numbering: content` is the default because it is what the Bukhārī CSV forced:
7,008 rows against references running to 7,563, no offset giving better than a
flat ~24% overlap.

## 6. Phases

Each stops at a gate. Figures pinned in `pipeline/tests/`.

### B-1 — Providers and field provenance *(no behaviour change)*

Introduce `pipeline/providers.py` with a merge that records a source per field.
Wire the existing sources through it. Output must be **byte-identical** to today.

*Gate:* the payload is unchanged; every field carries a source; all 41 tests and
243 browser assertions pass.

### B-2 — qalsadi as a provider — ✅ SHIPPED

Fill lemma/root/pos wherever the workbook lost them, at lower precedence than
the workbook's own non-null values.

*Gate:* the 409 lost-stem forms measured again — recovery should rise from 146
(36%) toward the low 300s. Held-out accuracy of qalsadi-sourced roots measured on
forms where the workbook has one, and published. `لِتَكُونَ` still wrong, and
still labelled wrong.

### B-3 — Witness-derived inventory — ✅ SHIPPED

Build the form inventory from the witness rather than the workbook. Keep the
workbook for gloss, curated senses and names.

*Gate:* the Tajrīd build reproduces its current tier composition within a point.
The 1,031 tokens whose witnessed vowelling has no lexicon entry drop toward zero.
A corpus with **no workbook** produces a working reader with glosses absent and
said to be absent.

### B-4 — Split the store — ✅ SHIPPED

`lexicon/` and `corpora/{id}/stats/` as separate shard sets. Shard counts already
derive from a byte budget, so this is a re-partition, not a re-design.

*Gate:* adding a second corpus adds lexicon entries without modifying existing
ones — assert the shared store is append-only for unchanged forms.

### D-1 — The aligner — ❌ MEASURED, NOT WORTH DOING

Anchored Needleman–Wunsch as above.

*Gate:* unmatched-token share falls from 6.1%; Tier 2 rises; held-out accuracy of
Tier 2 does not fall. Both must hold — coverage bought by accepting bad
alignments is worse than honest gaps, because the interface calls Tier 2 high
confidence.

### E-1 — Corrections — ✅ SHIPPED

`corpora/{id}/corrections.yaml`, keyed by stable `match_id` or
`(record, token)`, applied last, highest precedence, each entry carrying a note.

*Gate:* every error found by reading so far is in the file and asserted by a
test.

## 7. Order

```
B-1 ──> B-2 ──> B-3 ──> B-4
E-1   (independent, do first — smallest, and it compounds)
D-1   (independent of B; do after E-1)
```

B-1 first because it is the refactor that makes B-2 and B-3 additions rather than
rewrites. E-1 first in wall-clock terms because it is an afternoon and it stops
scholarship evaporating into chat logs.

## 8. What this buys

Adding a text becomes: a config file, a source URI, a vocalised witness. No
workbook, no bespoke frequency table, no new lexicon. The shared lexicon grows;
the corpus gets its own statistics and its own alignment.

And the failure modes stay legible, which is the property worth protecting: every
value a reader sees will say which provider it came from and how confident that
provider is.
