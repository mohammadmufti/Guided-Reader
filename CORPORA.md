# Corpora

This page lists the texts the reader serves. It gives the source of each text,
the evidence that vowels it, and the figures the build measures.

Written to ASD-STE100 Simplified Technical English. See `DOCS.md` for which
files use that standard and why.

---

## Summary

| Corpus | Records | Witnessed | Glosses | Source |
| --- | --- | --- | --- | --- |
| `tajrid` | 2,550 | 97.2% | own workbook | OpenITI |
| `muwatta` | 2,654 | 73.0% | shared | OpenITI |
| `nawawi40` | 137 | 94.0% | shared | OpenITI |
| `shahwaliullah40` | 80 | 100.0% | shared | sunnah.com scrape |

"Witnessed" is the share of body tokens in Tier 0, 1 or 2. The build measures
it. Each corpus declares its own threshold in `gates.min_witnessed_matn`.

---

## al-Tajrīd al-Ṣarīḥ (`tajrid`)

Al-Zabīdī (d. 893 AH) abridged Ṣaḥīḥ al-Bukhārī. This is that abridgement.

- **Text**: OpenITI, from a Shamela edition.
- **Vowels**: a vocalised Bukhārī, aligned record by record.
- **Meaning**: a hand-built frequency workbook with 22,464 readings and 21,028
  glosses.
- **Additions**: al-Ḍiyāʾ al-Dāghistānī added 88 hadith. The reader marks them
  and does not number them.

This corpus is the exception in two ways. It has a workbook, and no other text
does. It also numbers its hadith continuously, so the printed number addresses a
record without help.

---

## al-Muwaṭṭaʾ (`muwatta`)

Mālik b. Anas (d. 179 AH) collected these hadith and the settled practice of
Madina. This is the riwāya of Yaḥyā b. Yaḥyā al-Laythī.

- **Text**: OpenITI, from a Shamela edition.
- **Vowels**: a vocalised Laythī text, aligned record by record.
- **Meaning**: al-Tajrīd's glosses, shared through `match_id`.

**Choose the recension with care.** OpenITI holds nine Muwaṭṭaʾ versions. They
are different books, not different scans. The retrieval median shows this: the
Laythī text scores 0.963 against the witness, and al-Shaybānī's scores 0.617
against the same witness.

**The printed numbers do not address a record.** The edition starts again at 1 in
every kitāb. It also prints the same number more than once: hadith 13 occurs
three times in Kitāb al-Ḥajj. The reader therefore shows a running number, and
prints the edition's own number beside it as `ed. N`. Cite the edition number
with its kitāb.

Each kitāb title links to the same book on sunnah.com.

---

## al-Arbaʿūn al-Nawawiyya (`nawawi40`)

Al-Nawawī (d. 676 AH) gathered forty-two hadith. Ibn Rajab al-Ḥanbalī (d. 795
AH) added eight more.

- **Text**: OpenITI, from a Shamela edition that contains both.
- **Vowels**: a vocalised text of the forty-two, scraped from sunnah.com.
- **Meaning**: al-Tajrīd's glosses, shared through `match_id`.
- **Audio**: two reciters, Abū Usāma and Ḥāmid al-Darāhim.

**Ibn Rajab's ziyādāt are additions and hadith at the same time.** The reader
marks them as another hand's work. It also numbers them 43 to 50, because the
book is read and cited that way. Al-Tajrīd's zawāʾid are the other case: the
reader marks them and gives them no number.

Each hadith links to `sunnah.com/nawawi40:N`.

---

## al-Arbaʿūn li-Shāh Walī Allāh (`shahwaliullah40`)

Shāh Walī Allāh al-Dihlawī (d. 1176 AH) collected forty short hadith.

- **Text**: a scrape of sunnah.com, published as `AhmedBaset/hadith-json`.
- **Vowels**: none transferred. The source is 100% vowelled.
- **Meaning**: al-Tajrīd's glosses, shared through `match_id`.

This corpus differs from the others in three ways.

1. **OpenITI does not hold it.** The scrape is therefore the source text, not an
   alignment reference. Its words are redistributed. See `NOTICE.md`.
2. **The source arrives vowelled.** Every token carries harakāt, so the reader
   shows the edition's own vowels and infers nothing. No other text here does
   this.
3. **The source uses Persian letterforms.** The pipeline folds them to Arabic.
   This is the only place where the pipeline changes a letter. Section
   "Letterforms" below states the rule.

Each hadith links to `sunnah.com/shahwaliullah40:N`.

---

## The text is not changed

The reader shows the letters the source wrote. It adds harakāt from other
editions. It does not add, remove or move a letter.

This rule had one failure. `normalise()` folds hamza seats, tāʾ marbūṭa and alif
maqṣūra to match a word across editions. The reader then showed the matched
entry's spelling. It printed `الارض` as `الأرض`, `رحمه` as `رحمة`, and `يشتري`
as `يشترى`. That was 0.08% of al-Tajrīd's tokens and 0.90% of the Muwaṭṭaʾ's.

The binder now transfers marks only. Where a letter differs between the two
editions, the reader keeps the source's letter and drops that mark. `أن` and
`إن` are different words, not different vowellings.

A test measures this on every build. It must find zero differences.

### Letterforms

Persian and Urdu use codepoints for letters that Arabic already has. Shāh Walī
Allāh's source uses two of them: farsi yeh (U+06CC) and farsi kāf (U+06A9). No
other source here uses any.

These codepoints are outside the tokeniser's letter range. A word that contains
one is therefore not one word. `لَیْسَ` became `لَ` and `ْسَ`.

The pipeline folds them. The yeh needs care, because Persian writes one letter
where Arabic writes two:

- A final yeh after a kasra is a long *ī*. It becomes ي. Example: `فِیْ` becomes
  `فِيْ`.
- A final yeh after a fatḥa, or after a letter with no vowel, is alif maqṣūra.
  It becomes ى. Example: `عَلَی` becomes `عَلَى`.
- A yeh anywhere else becomes ي.

An earlier version folded every yeh to ي. That changed `عَلَی`, the preposition,
into `عَلَي`, the name ʿAlī.

---

## Add a corpus

Write one file: `pipeline/corpora/<id>.yaml`. Add no code.

See `ADDENDUM-adding-sources.md` for the fields. See `PIPELINE.md` for the
commands.

The four texts here differ in almost every way a text can differ. Each one
needed new configuration keys, and none needed a branch that names a book. If a
new text needs code, that is a fault in the pipeline, not in the text.
