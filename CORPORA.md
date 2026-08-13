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

Each kitāb title links to the same book on sunnah.com. The mapping is
**positional and declared so** (`match: position`): sunnah.com carries this
text as one page per book, 61 books in the same order with the same titles,
60 of 61 identical — verified against the sunnah.com-derived dataset and
pinned by a test. Positional mapping is legal only under that verification;
see "Chapter links" below for the mode a corpus gets by default, and for how
this corpus's links once vanished silently.

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
- **Vowels**: a sunnah.com text. 44% of tokens overall, but that headline
  misleads: the matn — the text the reader binds — is 90.1% vowelled, and
  the bare mass is al-Albānī's takhrīj apparatus (25.3%), unvowelled on the
  live site too. See DIACRITISATION.md §8.
- **Meaning**: al-Tajrīd's glosses, shared through `match_id`.

Three OpenITI versions exist. This one aligns to the witness at a median
coverage of 1.000. The longest carries a commentary and is a different book.

**Each hadith links to sunnah.com through the verified address map** — the
path form `bulugh/{book}/{pos}`, because the site has no complete
collection numbering for this book. See "External numbering" below.

---

## al-Shamāʾil al-Muḥammadiyya (`shamail`)

Al-Tirmidhī (d. 279 AH) collected 402 hadith on the person of the Prophet —
his appearance, his habits, his manner — rather than on rulings.

- **Text**: OpenITI, from a Shamela edition.
- **Vowels**: a sunnah.com text, 87.5% vowelled.
- **Meaning**: al-Tajrīd's glosses, shared through `match_id`.

57 bāb and no kitāb above them, so `heading_top_prefixes` is empty. Inventing
a top level would state a structure the book does not have.

**Each hadith links to sunnah.com through the verified address map** — the
colon form `shamail:{n}`; our 319 is the site's 317. See "External
numbering" below.

---

## External numbering

A corpus links each hadith to the same hadith on sunnah.com where the
correspondence is verified. For al-Tajrīd the editor states the Bukhārī
number himself; for Nawawī's Forty and Shāh Walī Allāh's the collections are
short and the numbering is checked; for Bulūgh al-Marām and al-Shamāʾil the
correspondence runs through a derived, verified address map — the mechanism
this section documents.

### How sunnah.com numbers a hadith, and why the scrape loses it

sunnah.com MERGES some hadith into one entry spanning two reference numbers.
Its chapter 1 page shows an entry headed `Ash-Shama'il Al-Muhammadiyah 5, 6` —
one entry, two numbers — whose in-book reference is Book 1, Hadith 5.

The Shamāʾil has **402 entries covering 417 reference numbers**, and 417 is
exactly the number of records in our text. The vocalisation witness (the
`AhmedBaset/hadith-json` scrape) keeps only the entry index (`idInBook`,
1–402) and discards the reference number, which is what a URL uses — so a
link built from `idInBook` lands on the wrong hadith, drifting further as
merges accumulate: `sunnah.com/shamail:317` serves the hadith that scrape
calls 306, which is our record 319. A first version of the link shipped on
exactly that assumption and was backed out.

### The address map

The site's own numbering was recovered from a second scrape of the same site
that kept what the first discarded — `CheeseWithSauce/HadithsJSONFormat`,
whose `reference` field preserves sunnah.com's reference tables verbatim.
`pipeline/sunnah_numbers.py` derives, for every witness entry, the address
the site itself uses, and refuses to write on any failure: the source is
pinned to a commit; every entry must match the witness at textual IDENTITY
(the two are scrapes of one site — overlap 1.000 on all 402 + 1,767 pairs,
re-measured on every run); the Shamāʾil's numbers must tile 1..417 exactly
with exactly 15 merges; and the hand-confirmed anchors must hold. Alignment
is positional WITHIN each chapter, because global position is not sound: the
site's chapter "8b" sits between 8 and 9 carrying numbers 368–369, and a
global zip mapped entry 306 to 319 where the confirmed answer is 317. The
committed maps (`pipeline/corpora/data/*_sunnah_links.json`, numbers only,
no text) are held to the same invariants by `tests/test_sunnah_links.py`.

The two collections turned out to need different address forms, measured on
live pages rather than assumed:

**al-Shamāʾil has a complete collection numbering**, 1..417, and
`sunnah.com/shamail:{n}` resolves every one. Its records link with the colon
form and display the site's number beside the heading where it differs from
ours.

**Bulūgh al-Marām has no complete numbering on sunnah.com.** Colon references
exist in five of its sixteen books — 378 entries — and the site assigns 31 of
those numbers twice. What is universal and unique is the path form
`sunnah.com/bulugh/{book}/{pos}`, which every entry carries (verified live:
`/bulugh/1/5` is the qullatayn hadith, `/bulugh/2/151` matches the map).
Bulūgh links with paths; the colon number, where the site has one, is shown
as the display number, and where it never assigned one the link shows no
number rather than inventing something.

### What links today

**Per hadith, through the map: Bulūgh and the Shamāʾil.** The binder stamps
the `idInBook` of the witness row each record aligned to — vouched for by
the alignment's coverage, filtered so the sequence never runs backwards
(retrieval is per record, and a short formulaic hadith occasionally matches
an unrelated row; 9 of Bulūgh's and 2 of the Shamāʾil's were dropped for
this, measured) — and the build TRANSLATES it through the map into the
site's address, never shipping the raw index. A witness index the map does
not know fails the build. Measured on the shipped payloads: 404 of the
Shamāʾil's 406 matn records link (99.5%), 1,566 of Bulūgh's 1,580 (99.1%);
the rest fall back to their chapter link, which is honest — a link the
binder could not vouch for does not exist.

**Per hadith, by shared numbering: al-Tajrīd (the editor's own Bukhārī
numbers), Nawawī's Forty and Shāh Walī Allāh's Forty** (`{n}` URLs, the
numbering checked; Ibn Rajab's ziyādāt are absent from the site and carry no
link).

**Per chapter, as the fallback and for the Muwaṭṭaʾ.** The Shamāʾil's 57 bāb
match sunnah.com's 57 chapters by title; Bulūgh's kitāb map 16 of 17 — its
ninth, `كتاب الطلاق`, is not a chapter on the site, so a positional map would
be off by one from there on; those 89 records reach the site through their
per-hadith links instead, which the chapter link never could. The Muwaṭṭaʾ
links each kitāb positionally (61-to-61, verified — sunnah.com has no
per-hadith pages for it). Position is otherwise only a fallback where the
counts agree — the Shamāʾil's 57 against 57, where a few chapters are titled
differently (`جلسة رسول الله` against `جلسته`) without disagreeing about
which chapter they are.

### Chapter links: two modes, and a guard

A `chapter_link` resolves its numbers in one of two declared ways. The
default, `match: title`, matches our headings to the witness JSON's
`chapters` by title, with position as a fallback only where the counts agree
— that is Bulūgh and the Shamāʾil above. `match: position` stamps our own
heading index, and is legal only where the corpus has verified the
positional correspondence itself — the Muwaṭṭaʾ, whose witness is a
single-column CSV with no chapter metadata and whose 61-to-61 map is checked
and pinned by a test.

The second mode exists because the first failed silently. When the Reader
moved from the Muwaṭṭaʾ's `kitab.index` to the build-stamped
`chapterLinkNumber`, title matching quietly required a JSON witness the
Muwaṭṭaʾ does not have: the matcher never ran, every number shipped null,
and `corpus.chapterLink` kept claiming a link the UI rendered on no record.
Nothing failed — the gates measure binding, not linking. The build now
refuses to ship a corpus that declares a `chapter_link` and resolves **zero**
chapters (partial resolution is a text fact — Bulūgh's الطلاق has no
counterpart; total failure is a configuration error), and a payload test
asserts the Muwaṭṭaʾ's links on the shipped files.

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
