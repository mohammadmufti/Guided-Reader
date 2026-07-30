# What you are trusting

This reader shows the vowelling, root, and meaning of every word in
al-Tajrīd al-Ṣarīḥ. Some of that is witnessed and some of it is inferred, and
the difference matters when you are learning. This page says which is which.

Every word panel ends with **How this reading was arrived at**. Open it.

---

## 1. The vowelling is not always certain

Half the words in this book have a spelling that could be read more than one
way — 49.7% of all tokens, on 2,631 ambiguous spellings. Each word is bound to a
dictionary entry in one of several ways, and the panel always tells you which.

| How the reading was arrived at | Share | Accuracy |
|---|--:|--:|
| Transferred from a vocalised Bukhārī edition at the aligned word | 49.5% | high |
| One entry matched, and its vowelling was witnessed | 45.8% | not in doubt |
| Inferred from the same phrase elsewhere in the book | 2.1% | **97.2%** |
| The most frequent reading of that spelling — a guess | 1.5% | **71.3%** |
| One entry matched, but its vowelling was itself a guess | 1.1% | consonants certain, vowels not |
| Not in the lexicon at all | 12 tokens | — |

The two accuracy figures are measured, not estimated. Tokens in the second row
have an independent witness, so hiding it and re-deriving the answer says what
the lower rows are worth. Those measurements live in the test suite and fail the
build if they stop being true.

**Roughly one word in every 66 is a guess.** Those carry a dotted underline.

A note on the fourth row, because it was wrong until recently. Earlier versions
said that when only one dictionary entry matched a spelling the reading was "not
in doubt". That is the wrong claim: it means the lexicon offered one option, not
that the option is correct. 1,354 tokens sit on an entry whose own vowelling was
the source data's most frequent guess rather than a witnessed reading — and in
`إِنَّمَا الْأَعْمَالُ` the single available option was the wrong case. Those
tokens now say so.

## 2. The classical entry is Lane's, unedited

The panel shows the entry for the word from Lane's *Arabic-English Lexicon*
(1863–1893) — where possible **the entry for that word specifically**, not a
sense picked from anywhere under its root. 83.2% of rooted forms are matched to
their own entry; the rest fall back to the first entry under the root, and the
panel says which you are looking at.

Nothing is selected on your behalf. The senses are Lane's, in Lane's order, with
his own labels (`b2`, `A2`) and his own source sigla. Two consequences worth
knowing:

- **Lane leads with morphology, not meaning.** The ṣalāh entry opens with two
  hundred words on orthography before reaching *"it signifies Prayer,
  supplication, or petition."* That is his ordering, and we have not reordered it.
- **The lexicon is Victorian.** The English is of its period, and Lane died
  before finishing; the later letters are thinner than the earlier ones.

Where a hand-curated literal/technical pair exists — 11.8% of tokens — it is
still the most reliable single thing on the panel.

*Earlier versions of this reader showed one mechanically sampled sense per root.
For ṣalāh that sample read "the middle of the back of a human being", which is a
real sense of the root — it is sense A2 of that very entry — and a catastrophic
thing to present as the meaning of the word. That field no longer exists.*

## 3. Some roots are wrong, and some were reconstructed

Root extraction fails predictably on hollow and irregular verbs — *kāna* and its
relatives. Where the two morphological analysers disagree, the panel warns above
the fold that **the root shown may be wrong**. Do not quietly ignore that line.

**409 forms lost their stem entirely.** The supplied analysis latched onto a
prefix and discarded the word: `وَلْيُحَدِّثْ`, "and let him relate", was recorded
as a particle with lemma `لِ` and no root. For **146 of them** the root has been
reconstructed by stripping the affixes and looking the remainder up elsewhere in
this same book — `يحدث` is here, correctly analysed, so حدث is recoverable. That
method is **98% accurate** on forms whose root is already known, and the panel
says when it has been used and which stem it went through. Nothing is invented:
every reconstructed root is one the source data already asserts for that stem.

The other **263** stay blank, because their stem does not occur on its own
anywhere in this book. Those say the root is *missing, not absent* — which is a
different statement from the one below.

Separately, about 48% of tokens have no root at all. That is not a failure:
particles, pronouns and proper nouns do not have one, and the panel says so.

## 4. The editorial layers are less reliable than the hadith

The hadith text is aligned against a fully vocalised edition of Bukhārī. The
author's preface, the chapter headings, and al-Ḍiyāʾ al-Dāghistānī's 88 added
hadith have no such target — nothing to align them against. Their vowelling
comes from the lower tiers, so treat it with more caution than the matn.

Zawāʾid additions are marked in the reading pane: *ليست من أصل الزبيدي*, not
from al-Zabīdī's original.

## 5. Two figures in the source workbook are wrong

Reported for honesty, since they are visible in the supplied data:

- `Tokens covered by root table: 0` is a bug. The real figure is 65,986 tokens,
  51.9%, which matches the workbook's own coverage table.
- `Tokens in matn layer: 124,885` matches nothing computable. Forms occurring
  only in matn give 36,973; forms occurring in matn at all give 125,926; the
  actual matn token count is 119,077. The last is the one this pipeline uses.

## 6. What this is not

No translation, no commentary, no audio. It shows you one hadith at a time and
tells you about the words in it.

Where the editor cites Ṣaḥīḥ al-Bukhārī — 2,222 of 2,254 hadith — that reference
links out to sunnah.com, which carries the full hadith with its isnād, its
chapter, and an English translation. None of that is held or reproduced here.

There is full-text search over the Arabic, by written form or by root. Form
search is exact; root search finds every derivative, and covers the 51.9% of
tokens that carry a root — particles do not have one. When a form search happens
to be spelled like a known root, the page offers the root search alongside it.

---

*Text: OpenITI, from a Shamela edition of al-Tajrīd al-Ṣarīḥ (Muʾassasat
al-Risāla, 1430/2009). Author died 893 AH; the work is public domain.
Vocalisation reference: a diacritised Ṣaḥīḥ al-Bukhārī, used to transfer
vowelling only — no Bukhārī text is redistributed here.*
