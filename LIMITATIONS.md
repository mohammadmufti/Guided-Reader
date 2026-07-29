# What you are trusting

This reader shows the vowelling, root, and meaning of every word in
al-Tajrīd al-Ṣarīḥ. Some of that is witnessed and some of it is inferred, and
the difference matters when you are learning. This page says which is which.

Every word panel ends with **How this reading was arrived at**. Open it.

---

## 1. The vowelling is not always certain

Half the words in this book have a spelling that could be read more than one
way — 49.7% of all tokens, on 2,631 ambiguous spellings. Each word is bound to
a dictionary entry in one of four ways, and the panel always tells you which.

| How the reading was arrived at | Share of the text | Accuracy |
|---|--:|--:|
| Only one entry matches the spelling | 50.3% | Not in doubt |
| Transferred from a vocalised Bukhārī edition at the aligned word | 46.0% | High |
| Inferred from the same phrase elsewhere in the book | 2.0% | **97.2%** |
| The most frequent reading of that spelling — a guess | 1.8% | **69.9%** |
| Not in the lexicon at all | 12 tokens | — |

The last two rows are measured, not estimated. Tokens in the second row have an
independent witness, so hiding it and re-deriving the answer says what the lower
tiers are worth: the inference rules are right 97.2% of the time and the
frequency fallback 69.9%. **Roughly one word in every 140 is a guess that is
probably right and might not be.** Those words carry a dotted underline.

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

## 3. Some roots are wrong, and the panel says so

Root extraction fails predictably on hollow and irregular verbs — *kāna* and its
relatives. Where the two morphological analysers disagree, the panel warns above
the fold that **the root shown may be wrong**. Do not quietly ignore that line.

Separately, about 48% of tokens have no root at all. That is not a failure:
particles, pronouns and proper nouns do not have one, and the panel says so
rather than showing an empty box.

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

No translation, no commentary, no corpus search, no audio. It shows you one
hadith at a time and tells you about the words in it.

---

*Text: OpenITI, from a Shamela edition of al-Tajrīd al-Ṣarīḥ (Muʾassasat
al-Risāla, 1430/2009). Author died 893 AH; the work is public domain.
Vocalisation reference: a diacritised Ṣaḥīḥ al-Bukhārī, used to transfer
vowelling only — no Bukhārī text is redistributed here.*
