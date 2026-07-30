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

**Ṣaḥīḥ al-Bukhārī, diacritised** — `abdelrahmaan/Hadith-Data-Sets`, which
states no licence. It is used **only as an alignment reference**, to transfer
vowelling onto words this project already holds. No Bukhārī text is
redistributed: `pipeline/cache/` is not committed, and the payload contains no
sentence from it. Where the editor cites Bukhārī, the reader is sent to
sunnah.com rather than shown the hadith here.

**The frequency workbook** — supplied by the maintainer. Its README records that
it was itself built from a Bukhārī alignment, `qalsadi`, Buckwalter/AraMorph and
Lane; three of those four are GPL, which is consistent with everything above.

## Attribution asked for, beyond the licences

- Taha Zerrouki, for `qalsadi`, `tashaphyne`, `arramooz` and `pyarabic`
- the `farahidi` authors, and the Alkhalil Morpho Sys team whose work it ports
- the OpenITI project
- the `laneslexicon` project, for a digitisation that would otherwise have taken
  years
