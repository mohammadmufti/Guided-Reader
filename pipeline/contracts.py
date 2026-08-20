"""
Data contracts for the Tajrid Reader pipeline — spec §5.

THIS FILE IS THE SINGLE SOURCE OF TRUTH.
`web/src/types/contracts.ts` is generated from it by `pipeline/codegen.py`.
Never hand-edit the TypeScript. Run `python pipeline/codegen.py` after changing
anything here; `--check` mode fails CI if the two have drifted.

Conventions enforced throughout the pipeline:
  * Nulls are preserved as `None` / `null`. Never coerce to "" or 0.
    The distinction between "absent by design" (a particle has no root) and
    "missing" (we failed to bind) is load-bearing — see spec §"Standing rules".
  * Every field that can be absent is typed `X | None`, not omitted.
"""

from __future__ import annotations

from typing import Annotated, Literal, TypedDict


class Doc:
    """Field documentation carried through to the generated TypeScript."""

    def __init__(self, text: str) -> None:
        self.text = text

    def __repr__(self) -> str:  # pragma: no cover - debugging aid
        return f"Doc({self.text!r})"


# --------------------------------------------------------------------------
# Enumerations
# --------------------------------------------------------------------------
# NOTE (Phase 0 finding): spec §5.1 lists four `layer` values and omits
# `heading_kitab`. The workbook's `first_record` column contains five
# namespaces — matn, zawaid, frontmatter, heading_bab, heading_kitab — and its
# `layers` column names all five. The data wins; `heading_kitab` is included.

RecordType = Literal["hadith", "kitab", "bab", "frontmatter"]
"""
What kind of thing a record is, for display and routing.

NOTE (Phase 1 finding): spec §5.1 lists a fifth value, `zawaid_note`, on the
assumption that the note line is itself a record. It is not. A zawa'id addition
is an unnumbered hadith body introduced by a `•` bullet; the note line
("this hadith is an addition of al-Diya' al-Daghistani…") merely terminates it
and is identical all 88 times. So the record is a `hadith` with layer `zawaid`,
and the note is carried on the record as `zawaidNote`. Confirmed by token count:
the workbook assigns 6,063 tokens to the zawaid layer and we reproduce 6,063
exactly, which only works if the bodies — not the notes — are the records.
"""

Layer = Literal["matn", "zawaid", "heading_bab", "heading_kitab", "frontmatter"]
"""Which textual layer a record belongs to. Mirrors the workbook's own names."""

Binding = Literal["source", "aligned", "unique", "heuristic", "unbound"]
"""How a token was bound to the lexicon. Tiers 0-5 of Phase 3.

`source` is Tier 0: the corpus file itself carried a full vowelling,
including a final short vowel, and it outranks both the aligned witness
and the workbook. Every corpus configured today is bare, so no token
currently carries it -- but a text taken from Shamela or a hadith dataset
rather than from OpenITI will, and discarding that would mean inferring an
answer the file already gave.
"""

Confidence = Literal["high", "medium", "low", "none"]
"""How much to trust the binding. Drives UI caveats, never hidden."""


# --------------------------------------------------------------------------
# 5.1 records.json
# --------------------------------------------------------------------------


class ReferenceLink(TypedDict):
    """
    Where an editorial cross-reference points.

    Corpus-specific, so it lives in `corpora/{id}.yaml`: al-Tajrid cites Sahih
    al-Bukhari, another text would cite something else. `url` carries a single
    `{n}` placeholder for the cited number.
    """

    label: str
    labelAr: str
    url: str


class AboutSource(TypedDict):
    """One row in the "about this book" sources list."""

    label: Annotated[str, Doc("Short name: 'Primary text', 'Classical apparatus'.")]
    detail: Annotated[str | None, Doc("A sentence on what it is and how it is used.")]
    url: Annotated[str | None, Doc("Where it lives, when it lives anywhere public.")]


class AboutAudioFile(TypedDict):
    label: Annotated[str, Doc("Display label: 'File 1'.")]
    url: Annotated[str, Doc("The recording's URL.")]


class CorpusAudio(TypedDict):
    note: Annotated[str | None, Doc("One line of context shown above the links.")]
    files: Annotated[list[AboutAudioFile], Doc("The recordings, in reading order.")]


class CorpusAbout(TypedDict):
    """The ⓘ popup's content, verbatim from corpora/{id}.yaml — the component
    holds no book knowledge; every corpus supplies its own."""

    description: Annotated[list[str], Doc("Paragraphs describing the book.")]
    sources: Annotated[list[AboutSource], Doc("Where the text and apparatus come from.")]
    audio: Annotated[
        CorpusAudio | None,
        Doc("Recitation links; playback is planned, links ship now."),
    ]


class CorpusMeta(TypedDict):
    """Provenance for the whole corpus. Rendered in the UI's colophon."""

    id: Annotated[str, Doc("Stable slug, matches the corpora/{id}.yaml filename.")]
    titleAr: Annotated[str, Doc("Title in Arabic, as printed.")]
    titleEn: Annotated[str, Doc("Romanised title.")]
    author: Annotated[str, Doc("Author name.")]
    authorDied: Annotated[str | None, Doc("Death date, e.g. '893 AH'. Null if unknown.")]
    sourceUri: Annotated[str, Doc("Canonical URI the text was fetched from.")]
    sourceRetrieved: Annotated[str, Doc("ISO date of retrieval.")]
    sourceSha256: Annotated[str, Doc("Checksum of the exact bytes parsed.")]
    edition: Annotated[str | None, Doc("Print edition the source encodes, if stated.")]
    referenceLink: Annotated[
        ReferenceLink | None,
        Doc("How to turn a `crossRefs` number into a URL. Null if the corpus cites nothing."),
    ]
    recordLink: Annotated[
        ReferenceLink | None,
        Doc(
            "How to turn THIS RECORD'S OWN number into a URL. Distinct from "
            "`referenceLink`, which resolves a number the text cites, and from "
            "`chapterLink`, which resolves the kitab. A forty-hadith collection "
            "cites nothing and has no kitab: its hadith N simply IS hadith N on "
            "sunnah.com. Null where the corpus has no such correspondence."
        ),
    ]
    asideLayer: Annotated[
        str | None,
        Doc("Layer name holding additions to the text, if the corpus has one."),
    ]
    asideNote: Annotated[
        str | None,
        Doc(
            "What to say beside an addition — whose it is, and that it is not "
            "part of the original. Al-Tajrid had this as a hardcoded Arabic "
            "sentence in the reader, which is one text's editorial fact living "
            "in every text's code."
        ),
    ]
    chapterLink: Annotated[
        ReferenceLink | None,
        Doc(
            "How to turn a KITAB INDEX into a URL, for a corpus whose external "
            "reference is per chapter rather than per hadith. sunnah.com gives "
            "the Muwatta' a page per book but no per-hadith anchor of the kind "
            "Bukhari has, so the honest link is to the chapter the hadith is "
            "in. Null where a corpus links per hadith, or not at all."
        ),
    ]
    about: Annotated[
        CorpusAbout | None,
        Doc("Content for the 'about this book' popup; None until a corpus writes one."),
    ]


class KitabRef(TypedDict):
    """The book (kitab) a record sits in."""

    index: int
    titleAr: str


class BabRef(TypedDict):
    """The chapter (bab) a record sits in."""

    index: int
    titleAr: str


class CorpusRecord(TypedDict):
    """One segmented unit of the corpus. Output of Phase 1."""

    id: Annotated[str, Doc("Record ID, e.g. 'matn-00005'. Matches workbook convention.")]
    number: Annotated[int | None, Doc(
        "Primary display number, and the ADDRESS: unique across the corpus, what "
        "`numberIndex` and the URL use. Null for headings and frontmatter."
    )]
    chapterLinkNumber: Annotated[
        int | None,
        Doc(
            "The external site's chapter number for this record, matched by "
            "TITLE rather than position — the two texts do not always divide "
            "into the same chapters. Null where this record's chapter has no "
            "counterpart."
        ),
    ]
    recordLinkNumber: Annotated[
        int | None,
        Doc(
            "The number to build `corpus.recordLink` with, or null where this "
            "record has no counterpart at the external site. Ibn Rajab's "
            "ziyadat are hadith 43-50 of Nawawi's Forty here and are absent "
            "from sunnah.com, so they carry no link."
        ),
    ]
    recordLinkRef: Annotated[
        str | None,
        Doc(
            "The external site's own address for this record, as a URL tail "
            "('shamail:317', 'bulugh/2/151'), where the corpus links through "
            "a verified address map — see pipeline/sunnah_numbers.py. When "
            "present, `corpus.recordLink.url` carries a `{ref}` placeholder "
            "and this fills it; `recordLinkNumber` is then the site's DISPLAY "
            "number, which can be null: sunnah.com never finished numbering "
            "Bulugh, so most of its hadith have an address but no number. "
            "Null for corpora whose numbering needs no map (the `{n}` form)."
        ),
    ]
    editionNumber: Annotated[int | None, Doc(
        "The number the printed edition gives this hadith, when it differs from "
        "`number`. On a text that restarts numbering in every kitab, `number` is a "
        "running count we assigned and matches no printed copy; this, with the "
        "kitab, is what a citation should quote. Null where the two agree."
    )]
    numbersCovered: Annotated[
        list[int],
        Doc(
            "Every display number this record covers. Normally one. The source puts hadith "
            "1201 and 1202 on a single opener line with no boundary to split on, so that "
            "record covers both and both resolve to it. Empty for headings and frontmatter."
        ),
    ]
    type: RecordType
    layer: Layer
    kitab: Annotated[KitabRef | None, Doc("Null for frontmatter.")]
    bab: Annotated[BabRef | None, Doc("Null for frontmatter and kitab headings.")]
    pages: Annotated[list[str], Doc("Page markers falling inside this record, in order.")]
    textRaw: Annotated[str, Doc("Extracted text with all structural markers stripped.")]
    seq: Annotated[int, Doc("1-based position in reading order. The suffix of `id`.")]
    # Reconciliation to an externally curated inventory's own record
    # numbering. al-Tajrid has one -- its workbook counts phantom records that
    # we do not emit, so `first_record` and `kwic` only resolve against this
    # index rather than against `seq`. No later corpus has such an inventory,
    # declares `curated_index_phantoms`, or carries this field.
    #
    # Named for the concept and not for the spreadsheet: a workbook is one way
    # to be curated, and the schema should outlive that particular one.
    curatedIndex: Annotated[
        int,
        Doc(
            "Index of this record in the WORKBOOK's record sequence, which runs 1..2640 "
            "because its pipeline emits an extra empty record after most kitab headings. "
            "Use this, not `seq`, to resolve the Surface sheet's `first_record` and `kwic`."
        ),
    ]
    tokens: Annotated[int, Doc("Token count under the workbook's tokenisation. See count_tokens().")]
    zawaidNote: Annotated[
        str | None, Doc("The al-Daghistani addition note, for zawaid records only. Null elsewhere.")
    ]
    crossRefs: Annotated[
        list[int],
        Doc(
            "Bukhari hadith numbers from the editorial `(بخاري: N)` reference. Empty when "
            "the record carries none. 2,207 of 2,254 hadith have one."
        ),
    ]
    prev: Annotated[str | None, Doc("Previous record ID in reading order. Null at the head.")]
    next: Annotated[str | None, Doc("Next record ID in reading order. Null at the tail.")]


class Navigation(TypedDict):
    """Reading order and the display-number lookup."""

    orderedIds: Annotated[list[str], Doc("Every record ID in reading order.")]
    numberIndex: Annotated[
        dict[str, str], Doc("Display number (as string) -> record ID. Gaps are simply absent.")
    ]
    audio: Annotated[
        list["AudioTrack"],
        Doc(
            "Recitations of this record, in the order they should be offered. "
            "Empty where none exists. A list rather than a single URL because a "
            "text may have more than one reciter and the reader should choose."
        ),
    ]


class RecordsFile(TypedDict):
    """`records.json` — the whole segmented corpus. Output of Phase 1."""

    corpus: CorpusMeta
    records: list[CorpusRecord]
    navigation: Navigation


# --------------------------------------------------------------------------
# 5.2 lexicon.json
# --------------------------------------------------------------------------


class SurfaceEntry(TypedDict):
    """
    One row of the workbook's `Surface` sheet, keyed by `match_id`.

    All 31 columns are preserved verbatim, nulls included. Field names keep the
    workbook's snake_case deliberately: renaming them would break the audit
    trail back to the source spreadsheet.
    """

    rank: int
    vocalized: str
    din_31635: Annotated[str | None, Doc("DIN 31635 transliteration.")]
    unvocalized: str
    freq: Annotated[int, Doc("Corpus-wide token frequency.")]
    pct: float
    cum_pct: float
    doc_freq: Annotated[int, Doc("Number of records the form appears in.")]
    pos: Annotated[str | None, Doc("Part of speech.")]
    lemma: str | None
    lemma_din: str | None
    root: Annotated[str | None, Doc("Null for ~48% of tokens BY DESIGN — particles, pronouns, proper nouns.")]
    voc_source: Annotated[str | None, Doc("How the vocalisation was chosen, e.g. 'aligned:4508'.")]
    morph_confidence: str | None
    pos_agreement: Annotated[str | None, Doc("'disagree' flags likely-wrong roots on hollow/irregular verbs.")]
    layers: Annotated[str | None, Doc("Layer distribution, e.g. 'matn:120,zawaid:3'.")]
    first_record: Annotated[str | None, Doc("Record ID of the FIRST occurrence only. Not a postings list.")]
    kwic: Annotated[str | None, Doc("Keyword-in-context for the first occurrence only.")]
    search_key: Annotated[str, Doc("Normalised join key. See normalise() — must reproduce exactly.")]
    gloss_msa: Annotated[str | None, Doc("Buckwalter-formatted gloss. Parse before display, never dump raw.")]
    lane_root: str | None
    classical_keywords: Annotated[str | None, Doc("The trustworthy classical field per the workbook README.")]
    classical_sense_sample: Annotated[str | None, Doc("ILLUSTRATIVE ONLY. Never present as the definition.")]
    classical_senses_more: str | None
    lane_entry_count: Annotated[int | None, Doc("Size of the full Lane entry the sample was drawn from.")]
    literal_sense: str | None
    technical_sense: str | None
    domain: str | None
    divergence: Annotated[str | None, Doc("curated | divergent | developed_sense | aligned | not_applicable | no_classical_entry | no_msa_gloss")]
    overlap_score: Annotated[float | None, Doc("Use for visual weighting only. Never print bare.")]
    match_id: Annotated[str, Doc("Primary key, '{search_key}#{n}', n ranking homographs by freq.")]


class LemmaEntry(TypedDict):
    """A row of the `Lemma` sheet, keyed by the vocalised dictionary form."""

    rank: int
    lemma: str
    search_key: str
    din_31635: str | None
    freq: int
    pct: float
    cum_pct: float
    n_surface_forms: Annotated[int, Doc("How many distinct surface forms realise this lemma.")]
    pos: str | None
    root: str | None
    gloss_msa: str | None
    lane_root: str | None
    keywords: Annotated[
        list[str],
        Doc(
            "The keyword cluster, filtered and ordered by distinctiveness. Lane's editorial "
            "vocabulary (tropical, assumed, termed, voce) and English function words are "
            "removed; genuine senses are kept regardless of how common they are."
        ),
    ]
    classical_keywords: Annotated[str | None, Doc("Raw source of `keywords`. Prefer `keywords`.")]
    lane_entry_count: int | None
    literal_sense: str | None
    technical_sense: str | None
    domain: str | None
    divergence: str | None
    overlap_score: float | None


class RootEntry(TypedDict):
    """
    A row of the `Root` sheet. CONTENT WORDS ONLY — the workbook suppresses
    roots for particles, pronouns and proper nouns, where they are spurious.
    """

    rank: int
    root: str
    search_key: str
    din_31635: str | None
    freq: int
    pct: float
    cum_pct: float
    n_surface_forms: int
    pos: str | None
    n_lemmas: int
    top_lemmas: Annotated[str | None, Doc("Comma-separated sample of lemmas under this root.")]
    gloss_msa: str | None
    lane_root: str | None
    keywords: Annotated[
        list[str],
        Doc(
            "The keyword cluster, filtered and ordered by distinctiveness. Lane's editorial "
            "vocabulary (tropical, assumed, termed, voce) and English function words are "
            "removed; genuine senses are kept regardless of how common they are."
        ),
    ]
    classical_keywords: Annotated[str | None, Doc("Raw source of `keywords`. Prefer `keywords`.")]
    lane_entry_count: int | None
    literal_sense: str | None
    technical_sense: str | None
    domain: str | None
    divergence: str | None
    overlap_score: float | None


class NameEntry(TypedDict):
    """A row of the `Names` gazetteer, mined from isnad attribution patterns."""

    name: str
    pattern_hits: Annotated[int, Doc("How many attribution patterns matched this name.")]


class TechnicalSenseEntry(TypedDict):
    """
    A row of `TechnicalSenses` — 86 hand-curated literal/technical pairs.
    Keyed by `key`, which is a search_key, not a vocalised form.
    """

    key: str
    root: Annotated[str | None, Doc("2 of 77 roots here are absent from the Root sheet.")]
    literal_sense: str | None
    technical_sense: str | None
    domain: str | None


class DivergenceEntry(TypedDict):
    """A row of the `Divergence` sheet, keyed by lemma. 3,313 rows."""

    rank: int
    lemma: str
    din_31635: str | None
    freq: int
    pos: str | None
    root: str | None
    gloss_msa: str | None
    literal_sense: str | None
    technical_sense: str | None
    keywords: Annotated[
        list[str],
        Doc(
            "The keyword cluster, filtered and ordered by distinctiveness. Lane's editorial "
            "vocabulary (tropical, assumed, termed, voce) and English function words are "
            "removed; genuine senses are kept regardless of how common they are."
        ),
    ]
    classical_keywords: Annotated[str | None, Doc("Raw source of `keywords`. Prefer `keywords`.")]
    classical_sense_sample: str | None
    divergence: str | None
    overlap_score: float | None


class ReviewCandidate(TypedDict):
    """One candidate vocalisation for an ambiguous form."""

    form: str
    refFreq: Annotated[
        int,
        Doc(
            "Frequency in the REFERENCE corpus used to pick the most-frequent vocalisation, "
            "not in this corpus. أبي occurs 190 times here but its top candidate is tagged 5433."
        ),
    ]


class ReviewEntry(TypedDict):
    """
    A row of the `Review` sheet: a form whose vocalisation is the most-frequent
    fallback rather than context-aligned. 3,349 of them.

    KEYED BY `unvocalized`, NOT `search_key`. In a 2,000-row sample, 1,997 keys
    matched Surface.unvocalized and only 1,346 matched Surface.search_key.
    Normalising before lookup silently misses a third of the sheet.
    """

    freq: int
    status: Annotated[str | None, Doc("e.g. lexicon_mfv — mirrors the voc_source vocabulary.")]
    nCandidates: int | None
    candidates: Annotated[
        list[ReviewCandidate] | None, Doc("Parsed from the sheet's pipe-delimited string.")
    ]
    layers: str | None
    firstRecord: str | None


class LexiconFile(TypedDict):
    """`lexicon.json` — output of Phase 2. All 31 Surface columns preserved, nulls intact."""

    surface: Annotated[dict[str, SurfaceEntry], Doc("match_id -> entry.")]
    searchKeyIndex: Annotated[
        dict[str, list[str]], Doc("search_key -> [match_id], ordered by DESCENDING freq.")
    ]
    lemmas: Annotated[dict[str, LemmaEntry], Doc("Keyed by vocalised dictionary form.")]
    roots: Annotated[dict[str, RootEntry], Doc("Keyed by root string.")]
    names: Annotated[dict[str, NameEntry], Doc("Keyed by name.")]
    technicalSenses: Annotated[dict[str, TechnicalSenseEntry], Doc("Keyed by search_key.")]
    divergence: Annotated[dict[str, DivergenceEntry], Doc("Keyed by lemma.")]
    review: Annotated[dict[str, ReviewEntry], Doc("Keyed by UNVOCALIZED form. See ReviewEntry.")]
    unvocalizedIndex: Annotated[
        dict[str, str], Doc("unvocalized form -> search_key. Bridges Review to the Surface table.")
    ]


# --------------------------------------------------------------------------
# 5.3 hadith/{id}.json
# --------------------------------------------------------------------------


class Token(TypedDict):
    """
    One word of a hadith as the reading pane renders it.

    `binding` and `confidence` are not decoration: they decide whether the
    token is clickable and whether its panel carries a caveat. Carry them
    end to end.
    """

    i: Annotated[int, Doc("Zero-based position within the record. Used by the ?w= deep link.")]
    surface: Annotated[str, Doc("Vocalised form if bound, raw form otherwise.")]
    raw: Annotated[str, Doc("The token exactly as it appeared in the source.")]
    matchId: Annotated[str | None, Doc("Lexicon key. Null when unbound.")]
    binding: Binding
    confidence: Confidence
    clickable: Annotated[bool, Doc("False for unbound tokens — they are visually inert.")]
    contextRoot: Annotated[
        str | None,
        Doc(
            "Root from context disambiguation, overriding the workbook. Set ONLY where the "
            "workbook gave a geminate and context gives a hollow root — the class where Lane "
            "backs context 18 of 18. 605 tokens."
        ),
    ]
    contextLemma: str | None
    punctuationAfter: Annotated[str, Doc("Trailing punctuation, kept out of the token proper.")]


class AudioTrack(TypedDict):
    """One recitation of one record."""

    label: str | None
    labelEn: str | None
    url: str


class HadithFile(TypedDict):
    """`hadith/{id}.json` — what the app actually fetches. Output of Phase 4."""

    id: str
    number: int | None
    chapterLinkNumber: int | None
    recordLinkNumber: int | None
    recordLinkRef: str | None
    editionNumber: int | None
    numbersCovered: list[int]
    type: RecordType
    layer: Layer
    kitab: KitabRef | None
    bab: BabRef | None
    pages: list[str]
    leading: Annotated[
        str,
        Doc(
            "Punctuation before the first token. `leading + sum(surface + punctuationAfter)` "
            "reproduces the record exactly, which is what lets the pane wrap each word "
            "in its own element without disturbing Arabic shaping."
        ),
    ]
    zawaidNote: str | None
    crossRefs: list[int]
    tokens: list[Token]
    prev: str | None
    next: str | None
    audio: Annotated[
        list[AudioTrack],
        Doc("Recitations of this record, in offer order. Empty where none exists."),
    ]


# --------------------------------------------------------------------------
# index.json — Phase 4 task 3
# --------------------------------------------------------------------------


class BabNode(TypedDict):
    """A chapter in the browsable tree."""

    index: int
    titleAr: str
    firstRecordId: str


class KitabNode(TypedDict):
    """A book in the browsable tree."""

    index: int
    titleAr: str
    firstRecordId: str
    babs: list[BabNode]


class ShardConfig(TypedDict):
    """
    How the lexicon is split. The client reimplements `hash` to route lookups.

    Counts are DERIVED at build time from a byte budget, not fixed — see
    `shard_count` in build.py. Read them from here; never hard-code them.
    """

    surface: Annotated[int, Doc(
        "Route STATISTICS by hash(search_key) % this. Per corpus."
    )]
    lexiconVersion: Annotated[
        str | None,
        Doc(
            "Content hash of the shared lexicon. The client puts it in the URL "
            "of every shared shard, so a rebuild invalidates the cache while a "
            "corpus switch does not. Null until share.py has run."
        ),
    ]
    sharedClassical: Annotated[int | None, Doc(
        "Route Lane HEADWORDS by hash(lane_root) % this, under data/lexicon/. "
        "Shared: Lane's Lexicon is the same book whichever text is being read."
    )]
    sharedLane: Annotated[int | None, Doc(
        "Route Lane ENTRIES by hash(nodeid) % this, under data/lexicon/. Shared "
        "for the same reason. Null until share.py has run."
    )]
    sharedSurface: Annotated[int | None, Doc(
        "Route lexical ENTRIES by hash(search_key) % this, under data/lexicon/. "
        "Shared across every corpus, because match_id is derived from the form "
        "and an entry is identical wherever it occurs. Null until share.py has "
        "run, in which case entries live under the corpus at `surface`."
    )]
    sharedLisan: Annotated[int | None, Doc(
        "Route Lisān ARTICLES by hash(lisan_root) % this, under data/lexicon/. "
        "Shared: the same book whichever text is being read. Null until "
        "share.py has run."
    )]
    sharedNihaya: Annotated[int | None, Doc(
        "Route al-Nihāya ARTICLES by hash(nihaya_root) % this, under "
        "data/lexicon/. Null until share.py has run."
    )]
    classical: Annotated[int, Doc("Route by hash(lane_root) % this.")]
    lane: Annotated[int, Doc("Route by hash(lane_root) % this.")]
    lisan: Annotated[int, Doc("Route by hash(lisan_root) % this.")]
    nihaya: Annotated[int, Doc("Route by hash(nihaya_root) % this.")]
    hash: Annotated[str, Doc("Hash name. 'fnv1a-32' — 32-bit FNV-1a over UTF-8 bytes.")]
    budgetBytes: Annotated[int, Doc("Per-shard brotli budget the counts were derived from.")]


class IndexCounts(TypedDict):
    """Headline counts, so the UI can show them without walking the tree."""

    records: int
    hadith: int
    kitab: int
    bab: int


class BindingTally(TypedDict):
    """
    Measured share of each provenance on this corpus's body layer.

    Published so the "what you are trusting" page can describe the book being
    read. It used to state al-Tajrid's figures for every corpus, which is false
    for one bound off a different witness and meaningless for one bound off its
    own harakat.
    """

    total: int
    source: float | None
    aligned: float | None
    unique: float | None
    uniqueUncertain: float | None
    heuristic: float | None
    unbound: float | None


class IndexFile(TypedDict):
    """`index.json` — navigation payload loaded once at boot. 12.3 KB brotli."""

    buildId: Annotated[
        str,
        Doc(
            "Content hash of the pipeline inputs. Append as ?v={buildId} to every hadith "
            "and shard request so those URLs can be cached immutably; index.json itself "
            "must revalidate, since it carries this value."
        ),
    ]
    buildCommit: Annotated[
        str,
        Doc(
            "Short SHA of the commit that built this payload; 'local' for a "
            "developer build. buildId hashes inputs and cannot distinguish "
            "two deploys of different code — this can."
        ),
    ]
    corpus: CorpusMeta
    navigation: Navigation
    tree: Annotated[list[KitabNode], Doc("Kitab/bab hierarchy for the jump-to browser.")]
    missingNumbers: Annotated[
        list[int],
        Doc(
            "Display numbers absent from the sequence. EMPTY for al-Tajrid: the spec "
            "expected ~13 gaps, but the only apparent one (1202) shares an opener line "
            "with 1201 and resolves to that record. Kept for other corpora."
        ),
    ]
    names: Annotated[dict[str, int], Doc("Proper-name gazetteer: name -> attribution hits.")]
    shards: ShardConfig
    binding: BindingTally
    counts: IndexCounts


# --------------------------------------------------------------------------
# The shipped panel payload — output of Phase 4, consumed by Phase 7
# --------------------------------------------------------------------------


class GlossSlot(TypedDict):
    """One morphological slot of a Buckwalter gloss: a clitic, or the stem."""

    senses: list[str]
    features: list[str] | None
    pos: str | None


class VerbForms(TypedDict):
    """
    A verb's two citation forms, and the scale they set.

    One form does not fix the scale: samiʿa could be yasmaʿu, yasmiʿu or
    yasmuʿu. Citing the pair is how the wazn is stated, and `pattern` states it
    directly — `يَ1ْ2َ3` for yafʿalu.
    """

    perfect: str
    imperfect: str
    pattern: str | None


class CliticSegment(TypedDict):
    """
    One stretch of a word: a proclitic, the stem, or a pronoun enclitic.

    `letters` is a COUNT, not text. The reader is shown the source's own
    spelling, and the analyser's is its own — sending its letters here would
    put another edition's word on the screen. A count lets the client colour
    the word it already has.

    `kind` only. NOT which prefix: CAMeL labels the types, and gets them wrong
    in plain cases — its disambiguator reads the emphatic lam of
    `إِنَّ الأمرَ لَيَسيرٌ` as a preposition.
    """

    kind: str
    letters: int


class Gloss(TypedDict):
    """
    A parsed `gloss_msa`. The raw string never reaches the client.

    `senses` is the STEM's sense list — what the reader wants. `before` and
    `after` are the clitic chain around it, `features` the morphological tags
    hoisted out of whichever slot carried them. Parsing happens once at build
    time against all 21,028 glosses rather than in the browser.
    """

    senses: list[str]
    features: list[str] | None
    before: list[GlossSlot]
    after: list[GlossSlot]
    stemPos: str | None


class RecoveredMorphology(TypedDict):
    """
    Morphology recovered from the corpus itself, where the supplied analysis
    lost it.

    409 forms carry `pos=particle`, a one-letter lemma and no root because the
    analyser latched onto a proclitic and discarded the word. The stem is
    usually attested elsewhere in the same corpus, correctly analysed:
    `وَلْيُحَدِّثْ` yields `يحدث`, which the workbook itself roots as حدث.

    Nothing here is invented — every value is one another row of the same
    workbook already asserts for the same stem. Accepted only when the gloss of
    the candidate stem corroborates the gloss of the input, which is what lifts
    held-out accuracy from 93.9% to 98.0%.
    """

    root: str
    lemma: str | None
    pos: str | None
    viaStem: Annotated[str, Doc("The stripped form that was looked up.")]
    sourceMatchId: Annotated[str, Doc("The lexicon row this evidence came from.")]
    accuracy: Annotated[float, Doc("Held-out accuracy of the recoverer, as a percentage.")]


class AnalysedMorphology(TypedDict):
    """
    Morphology from the analysers run directly — `qalsadi` for the lemma and
    part of speech, the `arramooz` dictionaries for the root.

    Present only where the workbook has nothing or lost the stem: it never
    overwrites a workbook value. 87.9% of forms resolve to a root this way
    against the workbook's 51.9% of tokens, and the two agree on 92.3% of the
    forms where both have an opinion.
    """

    lemma: str | None
    pos: str | None
    root: str | None
    rootAlternatives: Annotated[
        list[str], Doc("Other roots the dictionaries offer for the same lemma.")
    ]
    rootBasis: Annotated[
        str | None,
        Doc(
            "How the shown root was chosen. Two analyser stacks run: CAMeL "
            "(calima-msa-r13) and qalsadi+arramooz. 'agree' — both name this "
            "root, the strongest signal. 'camel' — they disagree; CAMeL's is "
            "shown (Lane sides with it 818:321 where they differ) and the "
            "other stack's stays in rootAlternatives. 'camel-only' — only "
            "CAMeL found one. 'arramooz-unanimous/-vocalised/-majority/"
            "-lane/-unresolved' — only the dictionary chain answered, with "
            "its own internal basis; '-unresolved' means the choice among "
            "dictionary rows is arbitrary and the panel must say so."
        ),
    ]


class CorpusStats(TypedDict):
    """
    How a form behaves in ONE corpus. Shipped separately from the lexical entry
    so that entry can be shared: everything here changes when the text changes,
    and nothing here is a property of the word.
    """

    freq: int
    doc_freq: int
    rank: int
    cum_pct: float
    layers: str | None
    boundFreq: int
    boundDocFreq: int


class PanelEntry(TypedDict):
    """
    A lexicon entry as the word panel receives it, keyed by match_id inside a
    surface shard. Trimmed from the 31-column workbook row: `kwic` and
    `first_record` are binding-verification data the reading pane never needs,
    and the classical apparatus lives in its own map keyed by `lane_root`
    because it is a function of the root, not of the surface form.
    """

    vocalized: str
    din_31635: str | None
    unvocalized: str
    freq: int
    pct: float
    cum_pct: float
    rank: int
    doc_freq: int
    pos: str | None
    lemma: str | None
    lemma_din: str | None
    root: Annotated[str | None, Doc("Null for ~48% of tokens BY DESIGN, not by failure.")]
    lane_root: str | None
    laneEntry: Annotated[
        str | None,
        Doc("Lane node id for THIS lemma's own entry, matched at build time. 83.2% of forms with a root."),
    ]
    nihaya_entry: Annotated[
        str | None,
        Doc("As lisan_entry, for al-Nihāya. Ordering, not a filter."),
    ]
    nihaya_root: Annotated[
        str | None,
        Doc(
            "Root of Ibn al-Athīr's al-Nihāya article, or null. NOT an "
            "attestation flag: the root-level signal fires on 84% of rooted "
            "forms and is flat across every frequency band, so it says almost "
            "nothing about whether a word is gharīb. It opens a section, and "
            "the copy must say 'Ibn al-Athīr's article on this root' rather "
            "than 'this word is gharīb'. Null for closed-class words."
        ),
    ]
    lisan_entry: Annotated[
        str | None,
        Doc(
            "Headword of the Lisān article this word most likely belongs to, "
            "when its key carries more than one root. `root_key` folds hamza "
            "so بدأ and بدا share a key; this says which. AN ORDERING, NOT A "
            "FILTER — the panel puts it first and leaves the other visible, "
            "because it is decided on the root's final radical and is right "
            "about fifteen times in sixteen. Null when there is nothing to "
            "choose between or nothing to choose on."
        ),
    ]
    lisan_root: Annotated[
        str | None,
        Doc(
            "Root of the Lisān al-ʿArab article, or null. There is NO entry-id "
            "companion: Ibn Manẓūr writes one article per root, so a word "
            "reaches its root's article or nothing, and the panel must say "
            "'the article on the root' rather than 'this word's own entry'. "
            "Always null for closed-class words — see build.py for the 7.6% "
            "of the corpus that measures."
        ),
    ]
    literal_sense: str | None
    technical_sense: str | None
    domain: str | None
    divergence: str | None
    overlap_score: Annotated[float | None, Doc("Visual weighting only. Never print bare.")]
    voc_source: str | None
    morph_confidence: str | None
    pos_agreement: Annotated[str | None, Doc("'disagree' means the root is probably wrong.")]
    layers: str | None
    reviewFlagged: bool
    boundFreq: Annotated[
        int,
        Doc(
            "How often THIS pipeline bound the entry. Not `freq`, which is the workbook's "
            "own count — the two differ on ~4% of tokens, deliberately."
        ),
    ]
    boundDocFreq: Annotated[int, Doc("Records containing it, by this pipeline's binding.")]
    isName: Annotated[bool, Doc("Present in the Names gazetteer — render as a person.")]
    analysed: Annotated[
        AnalysedMorphology | None,
        Doc("Direct analyser output, used only where the workbook has nothing."),
    ]
    fromWitness: Annotated[
        bool,
        Doc(
            "Minted from the vocalised witness: a reading the workbook's inventory lacked. "
            "916 entries. Vowelling witnessed, morphology from the analysers, no gloss."
        ),
    ]
    rootDisputed: Annotated[
        bool, Doc("The workbook and the analysers give different roots. Neither is authoritative.")
    ]
    rootPreferAnalysed: Annotated[
        bool,
        Doc(
            "True when BOTH analyser stacks independently agree on a root "
            "that contradicts the workbook's — the panel shows the agreed "
            "root and names the workbook's beside it. Measured basis: 1,922 "
            "workbook-analyser disputes; Lane sides with the analysers "
            "532:419; 528 are this both-agree class (فجئت, صدقة, سكت). "
            "entry.root itself stays the workbook's claim — display "
            "precedence, not data rewriting."
        ),
    ]
    recovered: Annotated[
        RecoveredMorphology | None,
        Doc("Set only when morphSuspect is true AND a stem was found. 146 of 409 forms."),
    ]
    morphSuspect: Annotated[
        bool,
        Doc(
            "The morphological analysis kept only a clitic and lost the stem — its lemma "
            "accounts for under 30% of the word. 409 forms, 940 tokens. Where this is true "
            "a null root means MISSING, not absent by design, and the panel must say so."
        ),
    ]
    gloss: Gloss | None
    lemmaVocalised: Annotated[
        str | None,
        Doc("The lemma with its harakat. `lemma` is the bare join key.")
    ]
    verb: Annotated[
        VerbForms | None,
        Doc("Perfect and imperfect, for a verb. Null otherwise."),
    ]
    segments: Annotated[
        list[CliticSegment] | None,
        Doc(
            "Clitic boundaries for this form, as letter counts in order. Null "
            "where the analyser could not segment it safely, and the word is "
            "then shown whole. About 92% of forms segment."
        ),
    ]
    glossQuick: Annotated[
        Gloss | None,
        Doc(
            "A short modern gloss from the morphological analyser, shown FIRST "
            "because it is the line a reader can use at a glance. Lane sits "
            "below and is deeper and older. Null where the analyser had "
            "nothing. Exists for words no workbook covers, which is most words "
            "in three of the four corpora."
        ),
    ]


class DictRun(TypedDict):
    """
    One inline run of a dictionary sense: plain text, Arabic, italic, or a ref.

    Inline content is flattened to runs rather than shipped as markup, so the
    client renders it without an HTML parser and no source can inject markup.
    That is a security boundary, not a convenience — every dictionary ingested
    into this store must flatten to these same runs.
    """

    t: Annotated[str, Doc('"t" text · "ar" Arabic · "i" italic · "ref" cross-reference · "q" quote · "trop" figurative')]
    v: str


class DictSense(TypedDict):
    """
    One sense of a dictionary entry.

    `label` and `level` carry the SOURCE'S OWN divisions and nothing invented.
    Lane's scheme is two-level — `A2` is a major division, `b3` a sub-sense —
    and `null` marks an entry's opening material, which carries the morphology
    and usually the primary signification. A source with no sense structure of
    its own must leave `label` null and say `level: "sentence"`; numbering
    divisions the author did not write is the sampling error this project
    already paid for once.
    """

    label: str | None
    level: Annotated[str, Doc("primary | major | sub | sentence")]
    runs: list[DictRun]


class DictEntry(TypedDict):
    """One headword entry under a root, e.g. صَلَاةٌ under صلو."""

    nodeid: Annotated[
        str,
        Doc(
            "Stable per-entry id, e.g. Lane's n24821. A source with one article "
            "per root and no per-headword entries uses the root itself."
        ),
    ]
    headword: str
    itypes: list[str] | None
    senses: list[DictSense]


class DictRoot(TypedDict):
    """
    Every entry one dictionary holds under one root, in that source's shard.

    This replaces v1's single sampled sense. The mean Lane root holds 15.8
    entries and 36 senses; v1 showed one sense, chosen mechanically, and for
    صلو that sense was "the middle of the back of a human being" — which is
    real, and is sense A2 of the صَلَاةٌ entry, not its definition.
    """

    root: str
    page: Annotated[int | None, Doc("Page in the source's own printed edition.")]
    vol: Annotated[
        int | None,
        Doc(
            "Volume, for a multi-volume source. Null for Lane, whose "
            "digitisation records a single page sequence."
        ),
    ]
    entries: list[DictEntry]


class ClassicalEntry(TypedDict):
    """
    Root-level summary in a classical shard: the keyword cluster and counts.

    The sampled sense that used to live here is gone — see DictRoot.
    """

    keywords: Annotated[
        list[str],
        Doc(
            "The keyword cluster, filtered and ordered by distinctiveness. Lane's editorial "
            "vocabulary (tropical, assumed, termed, voce) and English function words are "
            "removed; genuine senses are kept regardless of how common they are."
        ),
    ]
    classical_keywords: Annotated[str | None, Doc("Raw source of `keywords`. Prefer `keywords`.")]
    lane_entry_count: int | None
    nLemmas: int | None
    topLemmas: str | None
    rootFreq: int | None


# Emitted to TypeScript, in dependency order.
EXPORTED: list[type] = [
    AboutSource,
    AboutAudioFile,
    CorpusAudio,
    CorpusAbout,
    ReferenceLink,
    CorpusMeta,
    KitabRef,
    BabRef,
    CorpusRecord,
    Navigation,
    RecordsFile,
    SurfaceEntry,
    LemmaEntry,
    RootEntry,
    NameEntry,
    TechnicalSenseEntry,
    DivergenceEntry,
    ReviewCandidate,
    ReviewEntry,
    LexiconFile,
    Token,
    HadithFile,
    BabNode,
    KitabNode,
    DictRun,
    DictSense,
    DictEntry,
    DictRoot,
    ShardConfig,
    BindingTally,
    CliticSegment,
    VerbForms,
    AudioTrack,
    IndexCounts,
    IndexFile,
    GlossSlot,
    Gloss,
    AnalysedMorphology,
    RecoveredMorphology,
    CorpusStats,
    PanelEntry,
    ClassicalEntry,
]

# Old names for renamed contracts, emitted as TypeScript type aliases.
#
# The four dictionary types were called LaneRun/LaneSense/LaneEntry/LaneRoot
# when Lane's Lexicon was the only dictionary in the store. They were never
# Lane-specific in shape, and a second source made the name a lie. Renaming
# them alone would have been a breaking change to every importing component
# for no behavioural gain, so the old names stay reachable and the components
# migrate when they are next touched.
#
# NOT the same mechanism as EXPORTED_ALIASES above: that renders a Literal
# union, and `typing.get_args()` on a TypedDict returns () — putting one there
# emits `export type LaneRun = ;`, which is a syntax error that --check would
# happily pass through, because it compares text and does not parse TypeScript.
EXPORTED_TYPE_ALIASES: list[tuple[str, type]] = [
    ("LaneRun", DictRun),
    ("LaneSense", DictSense),
    ("LaneEntry", DictEntry),
    ("LaneRoot", DictRoot),
]

EXPORTED_ALIASES: list[tuple[str, object]] = [
    ("RecordType", RecordType),
    ("Layer", Layer),
    ("Binding", Binding),
    ("Confidence", Confidence),
]
