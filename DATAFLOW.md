# Data flow, end to end

This page follows one word from a remote file to the reader's screen. It states
every change the pipeline makes to the text, and where each lookup happens.

Written to ASD-STE100 Simplified Technical English. See `DOCS.md`.

---

## 1. Fetch

`fetch.py` downloads each source that the corpus config declares. It writes the
file to `cache/{corpus}/` and records a SHA-256 checksum in a manifest.

If a checksum changes, the build stops. A source that changes under you is a
different text, and the figures measured against the old one no longer hold.

Three kinds of source exist:

| Kind | Purpose | Redistributed? |
|---|---|---|
| `text` | The book itself. | Yes |
| `vocalisation_reference` | A vowelled edition, for alignment. | No |
| `lexicon` | A frequency workbook. Only al-Tajrīd has one. | Glosses only |

**No change is made to the bytes at this stage.**

---

## 2. Segment

`segment.py` turns the source into records. A record is one hadith, one heading,
or one block of front matter.

The line grammar is in `corpora/{id}.yaml`. This stage holds no Arabic that
names a book.

### Changes made here

The pipeline makes four changes to the text, and no others.

1. **Declared markup is removed.** Page markers such as `PageV12P34`, manuscript
   markers, `<div>` tags, and Shamela footnote references such as `(¬1)`. Each
   pattern is declared in the corpus config. A corpus that declares none loses
   nothing.
2. **Declared editorial apparatus is removed.** al-Tajrīd's `(بخاري: N)` cross
   references are captured as data, then removed from the text. The numbers
   reappear as links.
3. **Persian letterforms are folded to Arabic.** This applies to one corpus.
   See "Letterforms" in `CORPORA.md`.
4. **A JSON source is rendered into mARkdown.** Shāh Walī Allāh's text is a
   hadith array. `read_source` writes it as headings and body lines so that the
   rest of the stage does not need a second grammar.

**No letter is added, removed or changed, except in change 3.**

`tokenise.py` then splits each record. A token is a run of Arabic letters and
marks. `reconstruct()` asserts that the tokens rebuild the record exactly.

---

## 3. Analyse morphology

`analyse.py` runs two analysers over a list of forms:

- **CAMeL**, with the `calima-msa-r13` database.
- **qalsadi** with **arramooz**.

For each form it records a lemma, a part of speech, and a root. It chooses the
root in this order:

1. The vocalisation, where the two analysers disagree and one matches.
2. The majority, where more than one analyser agrees.
3. Lane, where a candidate root has an entry and the others do not.

It never chooses by alphabet. It records which basis it used, in `rootBasis`.

### What it reads

`analyse.py` reads three things:

1. al-Tajrīd's 22,464 workbook forms.
2. The readings the Bukhārī witness attests.
3. **Every token of every corpus.**

Item 3 was added after a measurement. The stage once read the workbook alone,
which belongs to al-Tajrīd. A word in another book that al-Tajrīd does not
contain was therefore never analysed. On the Muwaṭṭaʾ, 10,208 tokens bound to
nothing, and 111 of them had an analysis.

The stage now analyses 99,110 forms instead of 27,481. It finds a root for
93.4% of them.

The stage also records `lemmaVocalised`, the vocalised lemma CAMeL states in
its `lex` field. Clitics are stripped in it: `بَعَثَكَ` gives `بَعَث`. 91.1% of
analysed forms carry one.

### A remaining limit, measured

A root is not an article. Lane holds an article per headword, and an inflected
form is not a headword.

Two numbers bound what the lookup can reach:

- **Half of all entries have no Lane root.** 79% carry a root; 50% carry one
  that Lane has an article for. Lane does not hold every root, and a proper
  noun or a particle often has none.
- **The lookup is near its ceiling for the rest.** 85.0% of entries with a Lane
  root are linked. A fold-match against every headword and cited form in that
  root would reach 82.2%, so the tiered lookup already does better.

### What the reader actually opens

The reader opens Lane by ROOT. Where a word has no headword of its own, it
shows the first article under that root and says so. `كِتْمَان` is discussed
inside the article on `كَتَمَ` and is not a headword anywhere, so an exact match
can never succeed and the root is what matters.

Tokens that reach a Lane root:

| Corpus | Reaches a Lane root |
|---|--:|
| al-Tajrīd | 89.8% |
| al-Muwaṭṭaʾ | 82.2% |
| Nawawī's Forty | 73.2% |
| Shāh Walī Allāh | 92.6% |

Tokens whose own form matches a headword exactly are fewer: 44.7%, 27.1% and
15.6% for the first three. That number describes Lane's article inventory, not
this pipeline.

Adding `lemmaVocalised` moved these by half a point. It helps less than expected
for two reasons. CAMeL's `lex` is itself unvocalised for some words — `جاز`, not
`جَازَ` — so it cannot use the vocalised tier either. And Lane's article
inventory is form-specific: the `بعث` root is headed by the noun `بَعْثٌ`, and
no form-I verb headword exists there to match a verb lemma against.

The remaining gap is Lane's own structure, not the lookup.

---

## 4. Bind

`bind.py` gives each token a reading and a lexicon entry. It works in tiers. A
lower number wins.

| Tier | Evidence | Confidence |
|---|---|---|
| 0 | The source printed the vowels. | High |
| 1 | One lexicon entry matches the spelling. | High, or medium if that entry's own vowelling was a guess |
| 2 | A vocalised parent edition attests the reading at this position. | High |
| 3 | Syntax, or the same phrase elsewhere in this text. | Medium |
| 4 | The most frequent candidate. | Low |
| 5 | Nothing matched. | None |

`tiers.py` states which evidence each tier needs. A corpus without a witness
cannot reach Tier 2. A corpus without an inventory cannot reach Tiers 1, 3 or 4.

### How a corpus gets an inventory

al-Tajrīd reads its workbook. Every other corpus mints entries from the aligned
witness: `seed_from_witness` reads the witness as a word list, and each distinct
vowelled form becomes an entry.

### The join key

`normalise()` produces the key that matches a token to an entry. It folds hamza
seats, tāʾ marbūṭa and alif maqṣūra, so that two editions that spell a word
differently still match.

**The join key is not shown to the reader.** See section 6.

---

## 5. Enrich

The binder adds meaning from two places. Neither may change a reading.

1. **The glossary** (`build/glossary/glossary.json`). This holds al-Tajrīd's
   lexicography, keyed by `match_id`. A `match_id` is derived from the form, so
   the same reading is the same entry in every book.
2. **Sibling corpora**, through `lexicon_donors`.

A donor may state what a word MEANS. A donor may not introduce a reading that
this corpus's own evidence did not produce. Frequencies are never carried: they
describe one text.

---

## 6. Choose the letters to show

The binder shows the **source's** letters with the **witness's** marks.

`transfer_marks()` does this. It walks the two forms together. At each position
it writes the source's letter. It writes the witness's marks only where the two
letters agree.

This matters because `normalise()` folds letters to match. Without this step the
reader shows the matched entry's spelling. It once printed `الارض` as `الأرض`,
`رحمه` as `رحمة`, and `يشتري` as `يشترى`.

A test measures this on every build. It must find zero differences.

---

## 7. Look up Lane

`build.py` links each entry to one article in Lane's *Arabic-English Lexicon*.

The lookup needs a root. The root comes from the workbook, or from the glossary,
or from `analyse.py`.

With a root, the lookup tries three tiers in order:

1. **Vocalised.** Letters with their own short vowels, with the final case marks
   dropped. This tells `هِجْرَةٌ` from `هُجْرَةٌ`.
2. **Bare.** Letters only, with tāʾ marbūṭa preserved.
3. **Folded.** The `normalise()` key.

Within each tier it tries the entry's vocalised form first, then its lemma. The
lemma is often bare, and a bare candidate cannot separate six entries that share
a spelling.

### Headwords before forms

Lane holds 48 entries under the root `رجل`. Six share the bare spelling `رجل`.

Each article has a headword, and also cites other forms. The index is built in
two passes: **all headwords first, then all cited forms**. A headword is what an
article is about. A cited form is a word the article mentions.

Without the two passes, the article on the verb `رَجِلَ` claimed the key for
`رَجُل`, because it cites that form. Every occurrence of the noun `رَجُلٌ` then
opened an article about walking on foot.

### A known limit

The lookup uses the token's own form and its lemma. It does not strip clitics
first. A verb with an object clitic, such as `بَعَثَكَ`, does not match the verb
`بَعَثَ`, and falls back to a noun that shares the spelling. `للأب` has a
preposition and an article attached, and CAMeL's first root for it is `لب`
rather than `أبو`.

---

## 8. Build the payload

`build.py` writes one directory per corpus under `web/public/data/corpora/`.

It trims each entry to what the panel shows. It shards the lexicon to a byte
budget, measured on compressed bytes. It asserts that every reference resolves,
and that the panel payload stays under 100 ms.

`share.py` then merges the entries that corpora hold in common into
`web/public/data/lexicon/`. Lane's articles move there too: Lane is the same
book whichever text you read.

---

## 9. Serve

The reader fetches `corpora.json` first, to learn which books exist.

For a book it then fetches `index.json`, one record file per screen, and the
lexicon shards a word needs. Records and statistics come from the corpus
directory. Entries and Lane articles come from the shared directory.

The harakāt toggle removes marks at display time. It removes no letter.

---

## Summary: every change to the text

| Change | Where | Applies to |
|---|---|---|
| Remove declared markup | Segment | All corpora, per config |
| Remove declared apparatus | Segment | al-Tajrīd, Nawawī |
| Fold Persian letterforms | Segment | Shāh Walī Allāh only |
| Render JSON as mARkdown | Segment | Shāh Walī Allāh only |
| Add harakāt from a witness | Bind | Corpora with a witness |
| Remove harakāt on request | Reader | All, and reversible |

The pipeline makes no other change. It adds no letter and removes no letter.
