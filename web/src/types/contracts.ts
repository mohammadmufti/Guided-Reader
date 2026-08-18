// ---------------------------------------------------------------------------
// GENERATED FILE — DO NOT EDIT.
//
// Source of truth: pipeline/contracts.py
// Regenerate:     python pipeline/codegen.py
// Verify:         python pipeline/codegen.py --check
//
// Nulls are meaningful throughout. `root: string | null` means a null root is a
// real answer — particles and proper nouns have none — not a missing value.
// Do not widen these to optional (`?:`) and do not default them to "".
// ---------------------------------------------------------------------------

export type RecordType = "hadith" | "kitab" | "bab" | "frontmatter";

export type Layer = "matn" | "zawaid" | "heading_bab" | "heading_kitab" | "frontmatter";

export type Binding = "source" | "aligned" | "unique" | "heuristic" | "unbound";

export type Confidence = "high" | "medium" | "low" | "none";

/** One row in the "about this book" sources list. */
export interface AboutSource {
  /** Short name: 'Primary text', 'Classical apparatus'. */
  label: string;
  /** A sentence on what it is and how it is used. */
  detail: string | null;
  /** Where it lives, when it lives anywhere public. */
  url: string | null;
}

export interface AboutAudioFile {
  /** Display label: 'File 1'. */
  label: string;
  /** The recording's URL. */
  url: string;
}

export interface CorpusAudio {
  /** One line of context shown above the links. */
  note: string | null;
  /** The recordings, in reading order. */
  files: AboutAudioFile[];
}

/**
 * The ⓘ popup's content, verbatim from corpora/{id}.yaml — the component holds no book
 * knowledge; every corpus supplies its own.
 */
export interface CorpusAbout {
  /** Paragraphs describing the book. */
  description: string[];
  /** Where the text and apparatus come from. */
  sources: AboutSource[];
  /** Recitation links; playback is planned, links ship now. */
  audio: CorpusAudio | null;
}

/**
 * Where an editorial cross-reference points. Corpus-specific, so it lives in
 * `corpora/{id}.yaml`: al-Tajrid cites Sahih al-Bukhari, another text would cite something
 * else. `url` carries a single `{n}` placeholder for the cited number.
 */
export interface ReferenceLink {
  label: string;
  labelAr: string;
  url: string;
}

/** Provenance for the whole corpus. Rendered in the UI's colophon. */
export interface CorpusMeta {
  /** Stable slug, matches the corpora/{id}.yaml filename. */
  id: string;
  /** Title in Arabic, as printed. */
  titleAr: string;
  /** Romanised title. */
  titleEn: string;
  /** Author name. */
  author: string;
  /** Death date, e.g. '893 AH'. Null if unknown. */
  authorDied: string | null;
  /** Canonical URI the text was fetched from. */
  sourceUri: string;
  /** ISO date of retrieval. */
  sourceRetrieved: string;
  /** Checksum of the exact bytes parsed. */
  sourceSha256: string;
  /** Print edition the source encodes, if stated. */
  edition: string | null;
  /** How to turn a `crossRefs` number into a URL. Null if the corpus cites nothing. */
  referenceLink: ReferenceLink | null;
  /**
   * How to turn THIS RECORD'S OWN number into a URL. Distinct from `referenceLink`, which
   * resolves a number the text cites, and from `chapterLink`, which resolves the kitab. A
   * forty-hadith collection cites nothing and has no kitab: its hadith N simply IS hadith N on
   * sunnah.com. Null where the corpus has no such correspondence.
   */
  recordLink: ReferenceLink | null;
  /** Layer name holding additions to the text, if the corpus has one. */
  asideLayer: string | null;
  /**
   * What to say beside an addition — whose it is, and that it is not part of the original.
   * Al-Tajrid had this as a hardcoded Arabic sentence in the reader, which is one text's
   * editorial fact living in every text's code.
   */
  asideNote: string | null;
  /**
   * How to turn a KITAB INDEX into a URL, for a corpus whose external reference is per chapter
   * rather than per hadith. sunnah.com gives the Muwatta' a page per book but no per-hadith
   * anchor of the kind Bukhari has, so the honest link is to the chapter the hadith is in. Null
   * where a corpus links per hadith, or not at all.
   */
  chapterLink: ReferenceLink | null;
  /** Content for the 'about this book' popup; None until a corpus writes one. */
  about: CorpusAbout | null;
}

/** The book (kitab) a record sits in. */
export interface KitabRef {
  index: number;
  titleAr: string;
}

/** The chapter (bab) a record sits in. */
export interface BabRef {
  index: number;
  titleAr: string;
}

/** One segmented unit of the corpus. Output of Phase 1. */
export interface CorpusRecord {
  /** Record ID, e.g. 'matn-00005'. Matches workbook convention. */
  id: string;
  /**
   * Primary display number, and the ADDRESS: unique across the corpus, what `numberIndex` and
   * the URL use. Null for headings and frontmatter.
   */
  number: number | null;
  /**
   * The external site's chapter number for this record, matched by TITLE rather than position —
   * the two texts do not always divide into the same chapters. Null where this record's chapter
   * has no counterpart.
   */
  chapterLinkNumber: number | null;
  /**
   * The number to build `corpus.recordLink` with, or null where this record has no counterpart
   * at the external site. Ibn Rajab's ziyadat are hadith 43-50 of Nawawi's Forty here and are
   * absent from sunnah.com, so they carry no link.
   */
  recordLinkNumber: number | null;
  /**
   * The external site's own address for this record, as a URL tail ('shamail:317',
   * 'bulugh/2/151'), where the corpus links through a verified address map — see
   * pipeline/sunnah_numbers.py. When present, `corpus.recordLink.url` carries a `{ref}`
   * placeholder and this fills it; `recordLinkNumber` is then the site's DISPLAY number, which
   * can be null: sunnah.com never finished numbering Bulugh, so most of its hadith have an
   * address but no number. Null for corpora whose numbering needs no map (the `{n}` form).
   */
  recordLinkRef: string | null;
  /**
   * The number the printed edition gives this hadith, when it differs from `number`. On a text
   * that restarts numbering in every kitab, `number` is a running count we assigned and matches
   * no printed copy; this, with the kitab, is what a citation should quote. Null where the two
   * agree.
   */
  editionNumber: number | null;
  /**
   * Every display number this record covers. Normally one. The source puts hadith 1201 and 1202
   * on a single opener line with no boundary to split on, so that record covers both and both
   * resolve to it. Empty for headings and frontmatter.
   */
  numbersCovered: number[];
  type: RecordType;
  layer: Layer;
  /** Null for frontmatter. */
  kitab: KitabRef | null;
  /** Null for frontmatter and kitab headings. */
  bab: BabRef | null;
  /** Page markers falling inside this record, in order. */
  pages: string[];
  /** Extracted text with all structural markers stripped. */
  textRaw: string;
  /** 1-based position in reading order. The suffix of `id`. */
  seq: number;
  /**
   * Index of this record in the WORKBOOK's record sequence, which runs 1..2640 because its
   * pipeline emits an extra empty record after most kitab headings. Use this, not `seq`, to
   * resolve the Surface sheet's `first_record` and `kwic`.
   */
  curatedIndex: number;
  /** Token count under the workbook's tokenisation. See count_tokens(). */
  tokens: number;
  /** The al-Daghistani addition note, for zawaid records only. Null elsewhere. */
  zawaidNote: string | null;
  /**
   * Bukhari hadith numbers from the editorial `(بخاري: N)` reference. Empty when the record
   * carries none. 2,207 of 2,254 hadith have one.
   */
  crossRefs: number[];
  /** Previous record ID in reading order. Null at the head. */
  prev: string | null;
  /** Next record ID in reading order. Null at the tail. */
  next: string | null;
}

/** Reading order and the display-number lookup. */
export interface Navigation {
  /** Every record ID in reading order. */
  orderedIds: string[];
  /** Display number (as string) -> record ID. Gaps are simply absent. */
  numberIndex: Record<string, string>;
  /**
   * Recitations of this record, in the order they should be offered. Empty where none exists. A
   * list rather than a single URL because a text may have more than one reciter and the reader
   * should choose.
   */
  audio: AudioTrack[];
}

/** `records.json` — the whole segmented corpus. Output of Phase 1. */
export interface RecordsFile {
  corpus: CorpusMeta;
  records: CorpusRecord[];
  navigation: Navigation;
}

/**
 * One row of the workbook's `Surface` sheet, keyed by `match_id`. All 31 columns are preserved
 * verbatim, nulls included. Field names keep the workbook's snake_case deliberately: renaming
 * them would break the audit trail back to the source spreadsheet.
 */
export interface SurfaceEntry {
  rank: number;
  vocalized: string;
  /** DIN 31635 transliteration. */
  din_31635: string | null;
  unvocalized: string;
  /** Corpus-wide token frequency. */
  freq: number;
  pct: number;
  cum_pct: number;
  /** Number of records the form appears in. */
  doc_freq: number;
  /** Part of speech. */
  pos: string | null;
  lemma: string | null;
  lemma_din: string | null;
  /** Null for ~48% of tokens BY DESIGN — particles, pronouns, proper nouns. */
  root: string | null;
  /** How the vocalisation was chosen, e.g. 'aligned:4508'. */
  voc_source: string | null;
  morph_confidence: string | null;
  /** 'disagree' flags likely-wrong roots on hollow/irregular verbs. */
  pos_agreement: string | null;
  /** Layer distribution, e.g. 'matn:120,zawaid:3'. */
  layers: string | null;
  /** Record ID of the FIRST occurrence only. Not a postings list. */
  first_record: string | null;
  /** Keyword-in-context for the first occurrence only. */
  kwic: string | null;
  /** Normalised join key. See normalise() — must reproduce exactly. */
  search_key: string;
  /** Buckwalter-formatted gloss. Parse before display, never dump raw. */
  gloss_msa: string | null;
  lane_root: string | null;
  /** The trustworthy classical field per the workbook README. */
  classical_keywords: string | null;
  /** ILLUSTRATIVE ONLY. Never present as the definition. */
  classical_sense_sample: string | null;
  classical_senses_more: string | null;
  /** Size of the full Lane entry the sample was drawn from. */
  lane_entry_count: number | null;
  literal_sense: string | null;
  technical_sense: string | null;
  domain: string | null;
  /**
   * curated | divergent | developed_sense | aligned | not_applicable | no_classical_entry |
   * no_msa_gloss
   */
  divergence: string | null;
  /** Use for visual weighting only. Never print bare. */
  overlap_score: number | null;
  /** Primary key, '{search_key}#{n}', n ranking homographs by freq. */
  match_id: string;
}

/** A row of the `Lemma` sheet, keyed by the vocalised dictionary form. */
export interface LemmaEntry {
  rank: number;
  lemma: string;
  search_key: string;
  din_31635: string | null;
  freq: number;
  pct: number;
  cum_pct: number;
  /** How many distinct surface forms realise this lemma. */
  n_surface_forms: number;
  pos: string | null;
  root: string | null;
  gloss_msa: string | null;
  lane_root: string | null;
  /**
   * The keyword cluster, filtered and ordered by distinctiveness. Lane's editorial vocabulary
   * (tropical, assumed, termed, voce) and English function words are removed; genuine senses are
   * kept regardless of how common they are.
   */
  keywords: string[];
  /** Raw source of `keywords`. Prefer `keywords`. */
  classical_keywords: string | null;
  lane_entry_count: number | null;
  literal_sense: string | null;
  technical_sense: string | null;
  domain: string | null;
  divergence: string | null;
  overlap_score: number | null;
}

/**
 * A row of the `Root` sheet. CONTENT WORDS ONLY — the workbook suppresses roots for particles,
 * pronouns and proper nouns, where they are spurious.
 */
export interface RootEntry {
  rank: number;
  root: string;
  search_key: string;
  din_31635: string | null;
  freq: number;
  pct: number;
  cum_pct: number;
  n_surface_forms: number;
  pos: string | null;
  n_lemmas: number;
  /** Comma-separated sample of lemmas under this root. */
  top_lemmas: string | null;
  gloss_msa: string | null;
  lane_root: string | null;
  /**
   * The keyword cluster, filtered and ordered by distinctiveness. Lane's editorial vocabulary
   * (tropical, assumed, termed, voce) and English function words are removed; genuine senses are
   * kept regardless of how common they are.
   */
  keywords: string[];
  /** Raw source of `keywords`. Prefer `keywords`. */
  classical_keywords: string | null;
  lane_entry_count: number | null;
  literal_sense: string | null;
  technical_sense: string | null;
  domain: string | null;
  divergence: string | null;
  overlap_score: number | null;
}

/** A row of the `Names` gazetteer, mined from isnad attribution patterns. */
export interface NameEntry {
  name: string;
  /** How many attribution patterns matched this name. */
  pattern_hits: number;
}

/**
 * A row of `TechnicalSenses` — 86 hand-curated literal/technical pairs. Keyed by `key`, which
 * is a search_key, not a vocalised form.
 */
export interface TechnicalSenseEntry {
  key: string;
  /** 2 of 77 roots here are absent from the Root sheet. */
  root: string | null;
  literal_sense: string | null;
  technical_sense: string | null;
  domain: string | null;
}

/** A row of the `Divergence` sheet, keyed by lemma. 3,313 rows. */
export interface DivergenceEntry {
  rank: number;
  lemma: string;
  din_31635: string | null;
  freq: number;
  pos: string | null;
  root: string | null;
  gloss_msa: string | null;
  literal_sense: string | null;
  technical_sense: string | null;
  /**
   * The keyword cluster, filtered and ordered by distinctiveness. Lane's editorial vocabulary
   * (tropical, assumed, termed, voce) and English function words are removed; genuine senses are
   * kept regardless of how common they are.
   */
  keywords: string[];
  /** Raw source of `keywords`. Prefer `keywords`. */
  classical_keywords: string | null;
  classical_sense_sample: string | null;
  divergence: string | null;
  overlap_score: number | null;
}

/** One candidate vocalisation for an ambiguous form. */
export interface ReviewCandidate {
  form: string;
  /**
   * Frequency in the REFERENCE corpus used to pick the most-frequent vocalisation, not in this
   * corpus. أبي occurs 190 times here but its top candidate is tagged 5433.
   */
  refFreq: number;
}

/**
 * A row of the `Review` sheet: a form whose vocalisation is the most-frequent fallback rather
 * than context-aligned. 3,349 of them. KEYED BY `unvocalized`, NOT `search_key`. In a
 * 2,000-row sample, 1,997 keys matched Surface.unvocalized and only 1,346 matched
 * Surface.search_key. Normalising before lookup silently misses a third of the sheet.
 */
export interface ReviewEntry {
  freq: number;
  /** e.g. lexicon_mfv — mirrors the voc_source vocabulary. */
  status: string | null;
  nCandidates: number | null;
  /** Parsed from the sheet's pipe-delimited string. */
  candidates: ReviewCandidate[] | null;
  layers: string | null;
  firstRecord: string | null;
}

/** `lexicon.json` — output of Phase 2. All 31 Surface columns preserved, nulls intact. */
export interface LexiconFile {
  /** match_id -> entry. */
  surface: Record<string, SurfaceEntry>;
  /** search_key -> [match_id], ordered by DESCENDING freq. */
  searchKeyIndex: Record<string, string[]>;
  /** Keyed by vocalised dictionary form. */
  lemmas: Record<string, LemmaEntry>;
  /** Keyed by root string. */
  roots: Record<string, RootEntry>;
  /** Keyed by name. */
  names: Record<string, NameEntry>;
  /** Keyed by search_key. */
  technicalSenses: Record<string, TechnicalSenseEntry>;
  /** Keyed by lemma. */
  divergence: Record<string, DivergenceEntry>;
  /** Keyed by UNVOCALIZED form. See ReviewEntry. */
  review: Record<string, ReviewEntry>;
  /** unvocalized form -> search_key. Bridges Review to the Surface table. */
  unvocalizedIndex: Record<string, string>;
}

/**
 * One word of a hadith as the reading pane renders it. `binding` and `confidence` are not
 * decoration: they decide whether the token is clickable and whether its panel carries a
 * caveat. Carry them end to end.
 */
export interface Token {
  /** Zero-based position within the record. Used by the ?w= deep link. */
  i: number;
  /** Vocalised form if bound, raw form otherwise. */
  surface: string;
  /** The token exactly as it appeared in the source. */
  raw: string;
  /** Lexicon key. Null when unbound. */
  matchId: string | null;
  binding: Binding;
  confidence: Confidence;
  /** False for unbound tokens — they are visually inert. */
  clickable: boolean;
  /**
   * Root from context disambiguation, overriding the workbook. Set ONLY where the workbook gave
   * a geminate and context gives a hollow root — the class where Lane backs context 18 of 18.
   * 605 tokens.
   */
  contextRoot: string | null;
  contextLemma: string | null;
  /** Trailing punctuation, kept out of the token proper. */
  punctuationAfter: string;
}

/** `hadith/{id}.json` — what the app actually fetches. Output of Phase 4. */
export interface HadithFile {
  id: string;
  number: number | null;
  chapterLinkNumber: number | null;
  recordLinkNumber: number | null;
  recordLinkRef: string | null;
  editionNumber: number | null;
  numbersCovered: number[];
  type: RecordType;
  layer: Layer;
  kitab: KitabRef | null;
  bab: BabRef | null;
  pages: string[];
  /**
   * Punctuation before the first token. `leading + sum(surface + punctuationAfter)` reproduces
   * the record exactly, which is what lets the pane wrap each word in its own element without
   * disturbing Arabic shaping.
   */
  leading: string;
  zawaidNote: string | null;
  crossRefs: number[];
  tokens: Token[];
  prev: string | null;
  next: string | null;
  /** Recitations of this record, in offer order. Empty where none exists. */
  audio: AudioTrack[];
}

/** A chapter in the browsable tree. */
export interface BabNode {
  index: number;
  titleAr: string;
  firstRecordId: string;
}

/** A book in the browsable tree. */
export interface KitabNode {
  index: number;
  titleAr: string;
  firstRecordId: string;
  babs: BabNode[];
}

/**
 * One inline run of a dictionary sense: plain text, Arabic, italic, or a ref. Inline content
 * is flattened to runs rather than shipped as markup, so the client renders it without an HTML
 * parser and no source can inject markup. That is a security boundary, not a convenience —
 * every dictionary ingested into this store must flatten to these same runs.
 */
export interface DictRun {
  /** "t" text · "ar" Arabic · "i" italic · "ref" cross-reference · "q" quote · "trop" figurative */
  t: string;
  v: string;
}

/**
 * One sense of a dictionary entry. `label` and `level` carry the SOURCE'S OWN divisions and
 * nothing invented. Lane's scheme is two-level — `A2` is a major division, `b3` a sub-sense —
 * and `null` marks an entry's opening material, which carries the morphology and usually the
 * primary signification. A source with no sense structure of its own must leave `label` null
 * and say `level: "sentence"`; numbering divisions the author did not write is the sampling
 * error this project already paid for once.
 */
export interface DictSense {
  label: string | null;
  /** primary | major | sub | sentence */
  level: string;
  runs: DictRun[];
}

/** One headword entry under a root, e.g. صَلَاةٌ under صلو. */
export interface DictEntry {
  /**
   * Stable per-entry id, e.g. Lane's n24821. A source with one article per root and no
   * per-headword entries uses the root itself.
   */
  nodeid: string;
  headword: string;
  itypes: string[] | null;
  senses: DictSense[];
}

/**
 * Every entry one dictionary holds under one root, in that source's shard. This replaces v1's
 * single sampled sense. The mean Lane root holds 15.8 entries and 36 senses; v1 showed one
 * sense, chosen mechanically, and for صلو that sense was "the middle of the back of a human
 * being" — which is real, and is sense A2 of the صَلَاةٌ entry, not its definition.
 */
export interface DictRoot {
  root: string;
  /** Page in the source's own printed edition. */
  page: number | null;
  /**
   * Volume, for a multi-volume source. Null for Lane, whose digitisation records a single page
   * sequence.
   */
  vol: number | null;
  entries: DictEntry[];
}

/**
 * How the lexicon is split. The client reimplements `hash` to route lookups. Counts are
 * DERIVED at build time from a byte budget, not fixed — see `shard_count` in build.py. Read
 * them from here; never hard-code them.
 */
export interface ShardConfig {
  /** Route STATISTICS by hash(search_key) % this. Per corpus. */
  surface: number;
  /**
   * Content hash of the shared lexicon. The client puts it in the URL of every shared shard, so
   * a rebuild invalidates the cache while a corpus switch does not. Null until share.py has run.
   */
  lexiconVersion: string | null;
  /**
   * Route Lane HEADWORDS by hash(lane_root) % this, under data/lexicon/. Shared: Lane's Lexicon
   * is the same book whichever text is being read.
   */
  sharedClassical: number | null;
  /**
   * Route Lane ENTRIES by hash(nodeid) % this, under data/lexicon/. Shared for the same reason.
   * Null until share.py has run.
   */
  sharedLane: number | null;
  /**
   * Route lexical ENTRIES by hash(search_key) % this, under data/lexicon/. Shared across every
   * corpus, because match_id is derived from the form and an entry is identical wherever it
   * occurs. Null until share.py has run, in which case entries live under the corpus at
   * `surface`.
   */
  sharedSurface: number | null;
  /**
   * Route Lisān ARTICLES by hash(lisan_root) % this, under data/lexicon/. Shared: the same book
   * whichever text is being read. Null until share.py has run.
   */
  sharedLisan: number | null;
  /** Route by hash(lane_root) % this. */
  classical: number;
  /** Route by hash(lane_root) % this. */
  lane: number;
  /** Route by hash(lisan_root) % this. */
  lisan: number;
  /** Hash name. 'fnv1a-32' — 32-bit FNV-1a over UTF-8 bytes. */
  hash: string;
  /** Per-shard brotli budget the counts were derived from. */
  budgetBytes: number;
}

/**
 * Measured share of each provenance on this corpus's body layer. Published so the "what you
 * are trusting" page can describe the book being read. It used to state al-Tajrid's figures
 * for every corpus, which is false for one bound off a different witness and meaningless for
 * one bound off its own harakat.
 */
export interface BindingTally {
  total: number;
  source: number | null;
  aligned: number | null;
  unique: number | null;
  uniqueUncertain: number | null;
  heuristic: number | null;
  unbound: number | null;
}

/**
 * One stretch of a word: a proclitic, the stem, or a pronoun enclitic. `letters` is a COUNT,
 * not text. The reader is shown the source's own spelling, and the analyser's is its own —
 * sending its letters here would put another edition's word on the screen. A count lets the
 * client colour the word it already has. `kind` only. NOT which prefix: CAMeL labels the
 * types, and gets them wrong in plain cases — its disambiguator reads the emphatic lam of
 * `إِنَّ الأمرَ لَيَسيرٌ` as a preposition.
 */
export interface CliticSegment {
  kind: string;
  letters: number;
}

/**
 * A verb's two citation forms, and the scale they set. One form does not fix the scale: samiʿa
 * could be yasmaʿu, yasmiʿu or yasmuʿu. Citing the pair is how the wazn is stated, and
 * `pattern` states it directly — `يَ1ْ2َ3` for yafʿalu.
 */
export interface VerbForms {
  perfect: string;
  imperfect: string;
  pattern: string | null;
}

/** One recitation of one record. */
export interface AudioTrack {
  label: string | null;
  labelEn: string | null;
  url: string;
}

/** Headline counts, so the UI can show them without walking the tree. */
export interface IndexCounts {
  records: number;
  hadith: number;
  kitab: number;
  bab: number;
}

/** `index.json` — navigation payload loaded once at boot. 12.3 KB brotli. */
export interface IndexFile {
  /**
   * Content hash of the pipeline inputs. Append as ?v={buildId} to every hadith and shard
   * request so those URLs can be cached immutably; index.json itself must revalidate, since it
   * carries this value.
   */
  buildId: string;
  /**
   * Short SHA of the commit that built this payload; 'local' for a developer build. buildId
   * hashes inputs and cannot distinguish two deploys of different code — this can.
   */
  buildCommit: string;
  corpus: CorpusMeta;
  navigation: Navigation;
  /** Kitab/bab hierarchy for the jump-to browser. */
  tree: KitabNode[];
  /**
   * Display numbers absent from the sequence. EMPTY for al-Tajrid: the spec expected ~13 gaps,
   * but the only apparent one (1202) shares an opener line with 1201 and resolves to that
   * record. Kept for other corpora.
   */
  missingNumbers: number[];
  /** Proper-name gazetteer: name -> attribution hits. */
  names: Record<string, number>;
  shards: ShardConfig;
  binding: BindingTally;
  counts: IndexCounts;
}

/** One morphological slot of a Buckwalter gloss: a clitic, or the stem. */
export interface GlossSlot {
  senses: string[];
  features: string[] | null;
  pos: string | null;
}

/**
 * A parsed `gloss_msa`. The raw string never reaches the client. `senses` is the STEM's sense
 * list — what the reader wants. `before` and `after` are the clitic chain around it,
 * `features` the morphological tags hoisted out of whichever slot carried them. Parsing
 * happens once at build time against all 21,028 glosses rather than in the browser.
 */
export interface Gloss {
  senses: string[];
  features: string[] | null;
  before: GlossSlot[];
  after: GlossSlot[];
  stemPos: string | null;
}

/**
 * Morphology from the analysers run directly — `qalsadi` for the lemma and part of speech, the
 * `arramooz` dictionaries for the root. Present only where the workbook has nothing or lost
 * the stem: it never overwrites a workbook value. 87.9% of forms resolve to a root this way
 * against the workbook's 51.9% of tokens, and the two agree on 92.3% of the forms where both
 * have an opinion.
 */
export interface AnalysedMorphology {
  lemma: string | null;
  pos: string | null;
  root: string | null;
  /** Other roots the dictionaries offer for the same lemma. */
  rootAlternatives: string[];
  /**
   * How the shown root was chosen. Two analyser stacks run: CAMeL (calima-msa-r13) and
   * qalsadi+arramooz. 'agree' — both name this root, the strongest signal. 'camel' — they
   * disagree; CAMeL's is shown (Lane sides with it 818:321 where they differ) and the other
   * stack's stays in rootAlternatives. 'camel-only' — only CAMeL found one.
   * 'arramooz-unanimous/-vocalised/-majority/-lane/-unresolved' — only the dictionary chain
   * answered, with its own internal basis; '-unresolved' means the choice among dictionary rows
   * is arbitrary and the panel must say so.
   */
  rootBasis: string | null;
}

/**
 * Morphology recovered from the corpus itself, where the supplied analysis lost it. 409 forms
 * carry `pos=particle`, a one-letter lemma and no root because the analyser latched onto a
 * proclitic and discarded the word. The stem is usually attested elsewhere in the same corpus,
 * correctly analysed: `وَلْيُحَدِّثْ` yields `يحدث`, which the workbook itself roots as حدث.
 * Nothing here is invented — every value is one another row of the same workbook already
 * asserts for the same stem. Accepted only when the gloss of the candidate stem corroborates
 * the gloss of the input, which is what lifts held-out accuracy from 93.9% to 98.0%.
 */
export interface RecoveredMorphology {
  root: string;
  lemma: string | null;
  pos: string | null;
  /** The stripped form that was looked up. */
  viaStem: string;
  /** The lexicon row this evidence came from. */
  sourceMatchId: string;
  /** Held-out accuracy of the recoverer, as a percentage. */
  accuracy: number;
}

/**
 * How a form behaves in ONE corpus. Shipped separately from the lexical entry so that entry
 * can be shared: everything here changes when the text changes, and nothing here is a property
 * of the word.
 */
export interface CorpusStats {
  freq: number;
  doc_freq: number;
  rank: number;
  cum_pct: number;
  layers: string | null;
  boundFreq: number;
  boundDocFreq: number;
}

/**
 * A lexicon entry as the word panel receives it, keyed by match_id inside a surface shard.
 * Trimmed from the 31-column workbook row: `kwic` and `first_record` are binding-verification
 * data the reading pane never needs, and the classical apparatus lives in its own map keyed by
 * `lane_root` because it is a function of the root, not of the surface form.
 */
export interface PanelEntry {
  vocalized: string;
  din_31635: string | null;
  unvocalized: string;
  freq: number;
  pct: number;
  cum_pct: number;
  rank: number;
  doc_freq: number;
  pos: string | null;
  lemma: string | null;
  lemma_din: string | null;
  /** Null for ~48% of tokens BY DESIGN, not by failure. */
  root: string | null;
  lane_root: string | null;
  /** Lane node id for THIS lemma's own entry, matched at build time. 83.2% of forms with a root. */
  laneEntry: string | null;
  /**
   * Root of the Lisān al-ʿArab article, or null. There is NO entry-id companion: Ibn Manẓūr
   * writes one article per root, so a word reaches its root's article or nothing, and the panel
   * must say 'the article on the root' rather than 'this word's own entry'. Always null for
   * closed-class words — see build.py for the 7.6% of the corpus that measures.
   */
  lisan_root: string | null;
  literal_sense: string | null;
  technical_sense: string | null;
  domain: string | null;
  divergence: string | null;
  /** Visual weighting only. Never print bare. */
  overlap_score: number | null;
  voc_source: string | null;
  morph_confidence: string | null;
  /** 'disagree' means the root is probably wrong. */
  pos_agreement: string | null;
  layers: string | null;
  reviewFlagged: boolean;
  /**
   * How often THIS pipeline bound the entry. Not `freq`, which is the workbook's own count — the
   * two differ on ~4% of tokens, deliberately.
   */
  boundFreq: number;
  /** Records containing it, by this pipeline's binding. */
  boundDocFreq: number;
  /** Present in the Names gazetteer — render as a person. */
  isName: boolean;
  /** Direct analyser output, used only where the workbook has nothing. */
  analysed: AnalysedMorphology | null;
  /**
   * Minted from the vocalised witness: a reading the workbook's inventory lacked. 916 entries.
   * Vowelling witnessed, morphology from the analysers, no gloss.
   */
  fromWitness: boolean;
  /** The workbook and the analysers give different roots. Neither is authoritative. */
  rootDisputed: boolean;
  /**
   * True when BOTH analyser stacks independently agree on a root that contradicts the workbook's
   * — the panel shows the agreed root and names the workbook's beside it. Measured basis: 1,922
   * workbook-analyser disputes; Lane sides with the analysers 532:419; 528 are this both-agree
   * class (فجئت, صدقة, سكت). entry.root itself stays the workbook's claim — display precedence,
   * not data rewriting.
   */
  rootPreferAnalysed: boolean;
  /** Set only when morphSuspect is true AND a stem was found. 146 of 409 forms. */
  recovered: RecoveredMorphology | null;
  /**
   * The morphological analysis kept only a clitic and lost the stem — its lemma accounts for
   * under 30% of the word. 409 forms, 940 tokens. Where this is true a null root means MISSING,
   * not absent by design, and the panel must say so.
   */
  morphSuspect: boolean;
  gloss: Gloss | null;
  /** The lemma with its harakat. `lemma` is the bare join key. */
  lemmaVocalised: string | null;
  /** Perfect and imperfect, for a verb. Null otherwise. */
  verb: VerbForms | null;
  /**
   * Clitic boundaries for this form, as letter counts in order. Null where the analyser could
   * not segment it safely, and the word is then shown whole. About 92% of forms segment.
   */
  segments: CliticSegment[] | null;
  /**
   * A short modern gloss from the morphological analyser, shown FIRST because it is the line a
   * reader can use at a glance. Lane sits below and is deeper and older. Null where the analyser
   * had nothing. Exists for words no workbook covers, which is most words in three of the four
   * corpora.
   */
  glossQuick: Gloss | null;
}

/**
 * Root-level summary in a classical shard: the keyword cluster and counts. The sampled sense
 * that used to live here is gone — see DictRoot.
 */
export interface ClassicalEntry {
  /**
   * The keyword cluster, filtered and ordered by distinctiveness. Lane's editorial vocabulary
   * (tropical, assumed, termed, voce) and English function words are removed; genuine senses are
   * kept regardless of how common they are.
   */
  keywords: string[];
  /** Raw source of `keywords`. Prefer `keywords`. */
  classical_keywords: string | null;
  lane_entry_count: number | null;
  nLemmas: number | null;
  topLemmas: string | null;
  rootFreq: number | null;
}

// Compatibility aliases for renamed contracts.
export type LaneRun = DictRun;
export type LaneSense = DictSense;
export type LaneEntry = DictEntry;
export type LaneRoot = DictRoot;
