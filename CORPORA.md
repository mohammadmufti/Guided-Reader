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
| `bulugh` | 1,935 | 95.2% | shared | OpenITI |
| `shamail` | 463 | 95.0% | shared | OpenITI |

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

## Bulūgh al-Marām (`bulugh`)

Ibn Ḥajar al-ʿAsqalānī (d. 852 AH) collected the hadith the jurists reason
from, arranged by chapter of fiqh. 1,767 hadith.

- **Text**: OpenITI, from a Shamela edition.
- **Vowels**: a sunnah.com text, 44% vowelled — the thinnest witness here.
- **Meaning**: al-Tajrīd's glosses, shared through `match_id`.

Three OpenITI versions exist. This one aligns to the witness at a median
coverage of 1.000. The longest carries a commentary and is a different book.

**Its numbering is not sunnah.com's.** See "External numbering" below.

---

## al-Shamāʾil al-Muḥammadiyya (`shamail`)

Al-Tirmidhī (d. 279 AH) collected 402 hadith on the person of the Prophet —
his appearance, his habits, his manner — rather than on rulings.

- **Text**: OpenITI, from a Shamela edition.
- **Vowels**: a sunnah.com text, 87.5% vowelled.
- **Meaning**: al-Tajrīd's glosses, shared through `match_id`.

57 bāb and no kitāb above them, so `heading_top_prefixes` is empty. Inventing
a top level would state a structure the book does not have.

**Its numbering is not sunnah.com's.** See below.

---

## External numbering

A corpus links each hadith to the same hadith on sunnah.com where the two
numberings are known to agree. For al-Tajrīd the editor states the Bukhārī
number himself, and for Nawawī's Forty and Shāh Walī Allāh's the collections
are short and the numbering is checked.

**Bulūgh al-Marām and al-Shamāʾil link nowhere.** They were linked using the
`idInBook` field of the sunnah.com-derived dataset, on the assumption that it
is the number in a sunnah.com URL. It is not:

| | |
|---|---|
| `sunnah.com/shamail:317` serves | محمود بن غيلان … أم هانئ |
| the dataset calls that hadith | `idInBook` 306 |
| the dataset's own 317 is | a different report |

The alignment itself is sound — a record matches its dataset row at a median
coverage of 1.000, and that is what supplies the vowelling. What was never
verified is the step from dataset row to URL, and it cannot be verified from
this data: the dataset carries `id`, `idInBook` and `chapterId`, and none of
them is the site's hadith number.

### How sunnah.com numbers a hadith, and why the scrape loses it

sunnah.com MERGES some hadith into one entry spanning two reference numbers.
Its chapter 1 page shows an entry headed `Ash-Shama'il Al-Muhammadiyah 5, 6` —
one entry, two numbers — whose in-book reference is Book 1, Hadith 5.

That is the whole discrepancy. The Shamāʾil has **402 entries covering 417
reference numbers**, and 417 is exactly the number of records in our text.
The scrape keeps only the entry index (`idInBook`, 1–402) and discards the
reference number, which is what a URL uses.

Deriving one from the other needs the position of all 15 merges. Counting
isnād chains finds 15 — the right total — but places them wrongly: it puts 7
before entry 306 where the verified anchor requires 11. So the merges are not
recoverable from the scrape alone.

One anchor is confirmed: `sunnah.com/shamail:317` is entry 306, which is our
record 319.

To finish this, either request an API key from sunnah.com (their developer
page asks for a GitHub issue) and read `hadithNumber` for all 402 entries, or
harvest the 57 chapter pages, each of which lists every reference number it
contains.

### What links today

**al-Shamāʾil links to its chapter.** Our 57 bāb headings and sunnah.com's 57
chapters are the same chapters in the same order — chapter 1 is
`باب ما جاء في خلق رسول الله صلى الله عليه وسلم` on both, and the 29 headings
that differ do so only in spacing. The reader lands on the page containing
their hadith, with the chapter title visible, so an error would show rather
than hide.

**Bulūgh links to its kitāb**, matched by title. Its ninth is `كتاب الطلاق`,
which sunnah.com does not carry as a chapter of its own, so a positional map
would be off by one from there on and every later link would land in the wrong
book. 16 of 17 map; the 89 records of `كتاب الطلاق` carry no link.

Position is used only as a fallback, and only where both texts have the same
number of chapters in the same order — the Shamāʾil's 57 against 57, where a
few are titled differently without disagreeing about which chapter they are
(`جلسة رسول الله` against `جلسته`).

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
