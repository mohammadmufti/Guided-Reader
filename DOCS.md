# Documentation

This page says what each document is for, whether it is current, and which
writing standard it uses.

---

## Writing standard

Some documents here use **ASD-STE100 Simplified Technical English**. That
standard exists so that an aircraft maintenance instruction cannot be misread by
a reader who has no author to ask. The rules it applies:

- One instruction per sentence.
- 20 words per sentence for instructions, 25 for description.
- Active voice for anything you must do.
- Simple tenses only. No present perfect.
- One meaning per word, used the same way every time.
- Six sentences per paragraph. One topic per paragraph.
- Lists for sequences and conditions, not prose.
- Do not drop a verb, subject or article to make a sentence shorter.

Reference: <https://www.asd-ste100.org/>

### Where it applies, and where it does not

STE is flat and literal by design. Its own guidance says it is not for text
where voice and nuance carry meaning. This repository has both kinds of
document, so it uses STE for one kind and not the other.

**STE applies** to documents that tell you what to do or state what is true:

| File | Purpose |
| --- | --- |
| `PIPELINE.md` | The commands, in order. |
| `DEPLOY.md` | How a build reaches the site. |
| `ADDENDUM-adding-sources.md` | The fields a corpus config takes. |
| `CORPORA.md` | What each text is, and where it came from. |
| `DATAFLOW.md` | One word, from a remote file to the screen. |
| `DOCS.md` | This page. |

**STE does not apply** to documents that argue a case. These record why a
decision was made, and what was rejected. A rule that caps a sentence at 20
words and bans the present perfect removes the reasoning along with the length:

| File | Purpose |
| --- | --- |
| `SPEC.md` | What the reader promises, and the evidence for each promise. |
| `ARCHITECTURE.md` | Why the pipeline has these stages. |
| `DIACRITISATION.md` | Why vowelling is done this way and not another. |
| `LIMITATIONS.md` | What the reader gets wrong, measured. |
| `GAPS.md` | What is not solved. |
| `AUDIT.md` | What an audit found, and the measurements behind it. |
| `ROADMAP.md` | What is planned. |

`README.md` is mixed. Its instructions follow STE. Its explanation of what the
project is does not.

If you rewrite an argument document into STE, you will make it shorter and lose
the argument. That is the wrong trade in a repository whose main defence against
a wrong reading is that it wrote down why.

---

## Status

### Current

| File | Covers |
| --- | --- |
| `README.md` | What the project is. How to run it. |
| `CORPORA.md` | All four texts. |
| `DATAFLOW.md` | Every stage, and every change made to the text. |
| `PIPELINE.md` | Stage commands. |
| `DEPLOY.md` | CI and GitHub Pages. |
| `ADDENDUM-adding-sources.md` | Corpus config fields. |
| `SPEC.md` | Promises and gates. |
| `ARCHITECTURE.md` | Stage design. |
| `DIACRITISATION.md` | Vowelling strategy. |
| `LIMITATIONS.md` | Measured error rates. |
| `NOTICE.md` | Licences and provenance. Read before adding a source. |
| `GAPS.md` | Open problems. |
| `AUDIT.md` | The 2026 audit: findings, measurements, decisions. |
| `ROADMAP.md` | Planned work. |

### Superseded

**`MULTI-TEXT.md`** — this planned the move from one corpus to several. That
move is done. The repository now serves four texts, and the plan describes a
state it no longer has.

Keep the file for its record of what was tried. Do not use it to decide
anything. `CORPORA.md` and `ADDENDUM-adding-sources.md` describe the system as
it is.

---

## Figures in documents decay

Several documents quote measured figures. A figure in prose goes stale without
warning, so the test suite pins the ones that matter.

- `test_limitations.py` checks that `LIMITATIONS.md` quotes the shares the build
  produced.
- The `/about` page in the app quotes nothing. It reads `index.binding`, which
  the build measures for each corpus. An earlier version quoted al-Tajrīd's
  figures for every text, which was wrong for three of the four.

If you add a figure to a document, add a test for it, or expect it to become
false.
