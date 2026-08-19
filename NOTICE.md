# Third-party components and sources

This project is licensed **GPL-3.0-or-later** — see `LICENSE`. That is not a
preference; it follows from what the pipeline imports. Everything below is
recorded so the obligations, and the provenance of what a reader is shown, are
both checkable.

*This is a description of the licences involved, not legal advice.*

---

## Why GPL-3.0

The morphological analysis depends on Taha Zerrouki's Arabic NLP stack and on
`farahidi`, and every one of them is GPL:

| package | licence | used for |
|---|---|---|
| `farahidi` | GPL-3.0-or-later | context disambiguation (an Alkhalil Morpho Sys 2 port) |
| `qalsadi` | GPL | lemma and part of speech |
| `tashaphyne` | GPL | stemming, inside qalsadi |
| `arramooz` | GPL | the dictionary supplying roots |
| `camel-tools` | MIT | morphological analysis (root co-provider) |
| CALIMA-MSA-r13 | GPL-2 (Aramorph 1.2.1 lineage) | CAMeL's morphology database — © 2002 QAMUS LLC / Trustees of the University of Pennsylvania, distributed by the Linguistic Data Consortium. Used at build time; the database itself is not redistributed here |
| `pyarabic`, `libqutrub`, `naftawayh`, `alyahmor` | GPL | transitive dependencies |

`pipeline/` imports these directly, and publishing this repository is
distribution, so the pipeline is a derivative work and must carry the same
licence. The web application has no GPL dependency of its own, but it is
licensed the same way for coherence — a split licence across one repository
would be more trouble than it is worth here.

**What the GPL does not reach.** The output of a program is not covered by the
licence of the program merely by having been produced with it. The vowelling,
roots and statistics in `web/public/data/` are data, not a derived copy of any
of the software above. The one place this needs care is Lane — see below.

## Permissive dependencies

`pandas` (BSD-3), `brotli`, `openpyxl`, `PyYAML` (MIT). React, Vite, Tailwind,
React Router (MIT). These impose attribution only.

## Typefaces

**Amiri**, **Scheherazade New**, **Noto Naskh Arabic** and **Inter** are all
under the SIL Open Font License 1.1, obtained through Fontsource. The OFL
permits bundling and web use; it forbids selling the fonts on their own and
requires that Reserved Font Names not be used for modified versions. Nothing
here modifies them.

## Text and data

**al-Tajrīd al-Ṣarīḥ** — OpenITI, from a Shamela edition. The author died in
893 AH, so the work itself is public domain. OpenITI's corpus is distributed for
scholarly use; the edition encoded is Muʾassasat al-Risāla, Damascus,
1430/2009.

**Lane's *Arabic-English Lexicon*** — the text is public domain: Lane died in
1876 and the lexicon was published 1863–1893. **The digitisation is not.** It
comes from `laneslexicon/LexiconDatabase`, distributed under GPL-3.0, and this
project ingests and restructures 47,919 of its entries. A derived database is
the case where the GPL plausibly does reach the data, which is a second and
independent reason this repository is GPL-3.0.

**Lisān al-ʿArab** — the text is public domain: Ibn Manẓūr died in 711/1311.
The vocalised text is Shamela's own distribution of book 1687 (Dār Ṣādir, 3rd
ed. 1414 AH, 15 vols, with al-Yāzijī's notes), downloaded directly from
shamela.ws and committed at the repository root. The harakat are that edition's
editors' work — 8.4 million of them — and are reproduced as printed; none are
generated. Entry STRUCTURE comes from OpenITI, whose versions of this book are
all stripped of diacritics; the two are cross-validated at build time, and any
article whose de-diacritised Shamela text fails to reproduce the OpenITI text
keeps the OpenITI text instead.
The digitisation is Shamela's, distributed through OpenITI
(`0711IbnManzurIfriqi.LisanCarab.Shamela0001687-ara1`), and this project
ingests 9,152 of its entries into 8,973 root articles. The OpenITI version
metadata is complete and worth recording: annotated by SP Loynes, based on and
collated against OCLC 173667495 (Beirut: Dār Ṣādir), with pagination confirmed
identical to the first edition and the version marked `PRIMARY_VERSION`. The
volume and page shipped with each article are therefore citable against a
printed book. The `### $` entry markup this ingest joins on is deliberate
human annotation — the reviewer's note records tagging the second-level
headers "and all the entries" — not an artefact of conversion.

**al-Nihāya fī Gharīb al-Ḥadīth wa-l-Athar** — the text is public domain: Ibn
al-Athīr al-Jazarī died in 606/1210. The digitisation is Shamela's through
OpenITI (`0606IbnAthirMajdDin.NihayaFiGharib.Shamela0023691-ara1`), and 4,295
entries are ingested into 4,238 root articles. **Its provenance is materially
thinner than Lisān's, and the difference is recorded rather than smoothed
over:** that version's OpenITI metadata is an unfilled template — the annotator
field still reads "the name of the annotator", the date "YYYY-MM-DD", the base
"permalink, permalink, permalink". There is no recorded printed edition, so
there is nothing to cite the pagination to. The word panel says so, and the
config carries `provenance: unattested_edition` so nothing downstream can
quietly treat it as equivalent.

Neither text is redistributed whole. Both are filtered at build time to the
roots the corpora actually use, and `pipeline/cache/` is not committed.

**Ṣaḥīḥ al-Bukhārī, diacritised** — `abdelrahmaan/Hadith-Data-Sets`, which
states no licence. It is used **only as an alignment reference**, to transfer
vowelling onto words this project already holds. No Bukhārī text is
redistributed: `pipeline/cache/` is not committed, and the payload contains no
sentence from it. Where the editor cites Bukhārī, the reader is sent to
sunnah.com rather than shown the hadith here.

**al-Muwaṭṭaʾ** — OpenITI, from a Shamela edition of the riwāya of Yaḥyā b.
Yaḥyā al-Laythī. Mālik died in 179 AH, so the work is public domain.

**al-Arbaʿūn al-Nawawiyya, with Ibn Rajab's ziyādāt** — OpenITI, from a Shamela
edition. Al-Nawawī died in 676 AH and Ibn Rajab in 795 AH. Both are public
domain.

**al-Arbaʿūn li-Shāh Walī Allāh al-Dihlawī** — this one is different, and the
difference matters. The work is public domain: the author died in 1176 AH. But
it is in no OpenITI repository, and the only machine-readable copy is a scrape
of sunnah.com published as `AhmedBaset/hadith-json`. That copy is therefore the
**source text, not an alignment reference**, and unlike every other text here
its words *are* redistributed in the payload. sunnah.com states its own terms of
use. If those terms are a problem, this is the corpus to remove, and removing it
is one file: `pipeline/corpora/shahwaliullah40.yaml`.

**Vocalised Muwaṭṭaʾ and Nawawī texts** — `abdelrahmaan/Hadith-Data-Sets` and
`AhmedBaset/hadith-json`. Used **only as alignment references**, on the same
terms as the Bukhārī above: vowelling is transferred onto words this project
already holds, and no sentence from either is redistributed.

**sunnah.com address maps** — `pipeline/corpora/data/*_sunnah_links.json`,
derived by `pipeline/sunnah_numbers.py` from `CheeseWithSauce/HadithsJSONFormat`
(MIT-licensed, itself a scrape of sunnah.com that preserved the site's
reference tables). These committed files contain **numbers only** — for each
witness entry, the reference number or book-and-position sunnah.com itself
addresses that hadith with — and no text from any source. The scrape's text is
read transiently during derivation, for verification against the alignment
witness, and none of it is committed or shipped.

**The frequency workbook** — supplied by the maintainer. Its README records that
it was itself built from a Bukhārī alignment, `qalsadi`, Buckwalter/AraMorph and
Lane; three of those four are GPL, which is consistent with everything above.

## Attribution asked for, beyond the licences

- Taha Zerrouki, for `qalsadi`, `tashaphyne`, `arramooz` and `pyarabic`
- the `farahidi` authors, and the Alkhalil Morpho Sys team whose work it ports
- the OpenITI project
- `AhmedBaset/hadith-json` and `abdelrahmaan/Hadith-Data-Sets`, for machine
  -readable vocalised texts that no other source provides
- `CheeseWithSauce/HadithsJSONFormat`, for preserving sunnah.com's reference
  tables, without which the per-hadith links could not have been verified
- sunnah.com, from which all three of those datasets were scraped
- the `laneslexicon` project, for a digitisation that would otherwise have taken
  years
- SP Loynes and the OpenITI annotators, whose hand-tagged dictionary entries in
  Lisān al-ʿArab are what make it joinable to a root at all
