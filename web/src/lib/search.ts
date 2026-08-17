import type { IndexFile } from "@/types/contracts";
import {
  loadCorpora,
  loadIndexOf,
  loadRecordOf,
  getCorpus,
} from "@/lib/data";
import { normalise, rootKey } from "@/lib/normalise";

const ROOT = `${import.meta.env.BASE_URL}data`;

interface SearchFile {
  buildId: string;
  /** Per key: one entry per record, `[deltaSeq, tokenIndex, tokenIndex, ...]`. */
  postings: Record<string, number[][]>;
  /** Same shape, keyed by root. 2,176 roots over 51.9% of tokens. */
  roots: Record<string, number[][]>;
}

/** One record containing a word, and every position it occupies in it. */
export interface Posting {
  seq: number;
  positions: number[];
}

interface CorpusSearch {
  postings: Map<string, Posting[]>;
  roots: Map<string, Posting[]>;
}

// One cache PER CORPUS, keyed explicitly, loaded lazily. The previous shape
// — one module-level index with a "whose is it?" check bolted on after a
// corpus-switch bug — is subsumed: postings are record sequence numbers,
// meaningful only against their own book's ordered ids, so the index and
// the book travel together in the key and the bug class has nowhere to
// live. Cross-corpus search then falls out: it is just this cache asked
// for several books.
const searchCache = new Map<string, Promise<CorpusSearch>>();

function loadSearchOf(corpus: string): Promise<CorpusSearch> {
  let p = searchCache.get(corpus);
  if (!p) {
    p = (async () => {
      const index = await loadIndexOf(corpus);
      const res = await fetch(
        `${ROOT}/corpora/${corpus}/search.json?v=${index.buildId}`,
      );
      if (!res.ok) throw new Error(`${corpus}/search.json: HTTP ${res.status}`);
      const file = (await res.json()) as SearchFile;
      const expand = (src: Record<string, number[][]>) => {
        const out = new Map<string, Posting[]>();
        for (const [key, entries] of Object.entries(src)) {
          const list: Posting[] = [];
          let acc = 0;
          for (const entry of entries) {
            acc += entry[0]!;
            list.push({ seq: acc, positions: entry.slice(1) });
          }
          out.set(key, list);
        }
        return out;
      };
      return { postings: expand(file.postings), roots: expand(file.roots ?? {}) };
    })();
    searchCache.set(corpus, p);
  }
  return p;
}

export interface Occurrence {
  id: string;
  number: number | null;
  /** Value for `?w=` — bare index, or `recordId:index` for an unnumbered record. */
  target: string;
  index: number;
  snippet: { text: string; match: boolean }[];
  /** How this occurrence was vowelled — the same spelling is not always read the same way. */
  surface: string;
}

const MAX_OCCURRENCES = 24;

/**
 * Every other place a spelling occurs, with context. CURRENT BOOK only, by
 * design: the panel's offered count (`doc_freq`) is measured over this
 * corpus, and the offer must deliver exactly what it promised.
 *
 * Deliberately NOT fetched with the panel. The index is 310 KB and most panels
 * are opened to read a gloss, so it loads only when a reader asks for it.
 *
 * Filtered to THIS reading, not merely this spelling. `صلاه` is one search key
 * covering six vocalisations, so an unfiltered lookup returns four times what
 * the panel offered — the count comes from `freq`, which is per match_id.
 * Promising six and delivering twenty-four is worse than not offering at all.
 */
export async function loadOccurrences(
  matchId: string,
  index: IndexFile,
  exclude?: { id: string; index: number },
): Promise<{ total: number; shown: Occurrence[] }> {
  const corpus = getCorpus();
  const searchKey = matchId.slice(0, matchId.lastIndexOf("#"));
  const { postings } = await loadSearchOf(corpus);
  const list = postings.get(searchKey) ?? [];
  const order = index.navigation.orderedIds;
  const numberOf = new Map<string, number>();
  for (const [num, id] of Object.entries(index.navigation.numberIndex)) {
    if (!numberOf.has(id)) numberOf.set(id, Number(num));
  }

  // A record without a display number — a zawa'id addition or a heading — is
  // still reachable, but through the numbered record it sits under, using the
  // record-scoped selection syntax. Linking to /hadith/null was the bug here.
  const ownerOf = (seq: number): { number: number | null; recordId: string } => {
    for (let s = seq; s >= 1; s--) {
      const id = order[s - 1];
      if (id && numberOf.has(id)) return { number: numberOf.get(id)!, recordId: order[seq - 1]! };
    }
    return { number: null, recordId: order[seq - 1]! };
  };

  const candidates: { id: string; index: number; seq: number }[] = [];
  for (const p of list) {
    const id = order[p.seq - 1];
    if (!id) continue;
    for (const i of p.positions) {
      if (exclude && exclude.id === id && exclude.index === i) continue;
      candidates.push({ id, index: i, seq: p.seq });
    }
  }

  // Keep only the tokens bound to THIS entry. Requires reading the records, so
  // stop once enough have been found rather than walking every candidate.
  const flat: { id: string; index: number; seq: number }[] = [];
  for (const c of candidates) {
    const rec = await loadRecordOf(corpus, c.id, index.buildId);
    if (rec.tokens[c.index]?.matchId === matchId) flat.push(c);
    if (flat.length >= MAX_OCCURRENCES) break;
  }

  const page = flat;
  const shown = await Promise.all(
    page.map(async ({ id, index: i, seq }) => {
      const rec = await loadRecordOf(corpus, id, index.buildId);
      const owner = ownerOf(seq);
      const lo = Math.max(0, i - 5);
      const hi = Math.min(rec.tokens.length, i + 6);
      const parts: { text: string; match: boolean }[] = [];
      if (lo > 0) parts.push({ text: "… ", match: false });
      for (let k = lo; k < hi; k++) {
        parts.push({ text: rec.tokens[k]!.surface, match: k === i });
        parts.push({ text: rec.tokens[k]!.punctuationAfter, match: false });
      }
      if (hi < rec.tokens.length) parts.push({ text: " …", match: false });
      return {
        id,
        number: owner.number,
        // Bare index when the occurrence is in the numbered record itself;
        // record-scoped when it is in an addition beneath it.
        target: numberOf.has(id) ? String(i) : `${id}:${i}`,
        index: i,
        snippet: parts,
        surface: rec.tokens[i]?.surface ?? "",
      };
    }),
  );
  return { total: flat.length, shown };
}

export interface Hit {
  /** The book this hit lives in — every link must carry it. */
  corpus: string;
  seq: number;
  id: string;
  number: number | null;
  kitab: string | null;
  snippet: { text: string; match: boolean }[];
  matched: number;
}

/** One book's section of a result list. */
export interface BookHits {
  corpus: string;
  titleAr: string | null;
  hits: Hit[];
  total: number;
}

export type Mode = "form" | "root";

const MAX_RESULTS = 40;
const PER_BOOK = 6;
const SNIPPET_RADIUS = 7;

/**
 * The numbered record a sequence position belongs to — itself when numbered,
 * else the numbered record it sits under (a heading or an addition). A
 * search hit on a bab title used to link to /read/null.
 */
function ownerNumber(
  seq: number,
  order: readonly string[],
  numberOf: Map<string, number>,
): number | null {
  for (let s = seq; s >= 1; s--) {
    const id = order[s - 1];
    if (id && numberOf.has(id)) return numberOf.get(id)!;
  }
  for (let s = seq + 1; s <= order.length; s++) {
    const id = order[s - 1];
    if (id && numberOf.has(id)) return numberOf.get(id)!;
  }
  return null;
}

/** A window around the first match, with the matching words flagged. */
function buildSnippet(
  tokens: { surface: string; raw: string; punctuationAfter: string }[],
  terms: string[],
): { text: string; match: boolean }[] {
  const isMatch = tokens.map((t) => terms.includes(normalise(t.raw)));
  const first = isMatch.indexOf(true);
  const centre = first === -1 ? 0 : first;
  const lo = Math.max(0, centre - SNIPPET_RADIUS);
  const hi = Math.min(tokens.length, centre + SNIPPET_RADIUS + 1);

  const parts: { text: string; match: boolean }[] = [];
  if (lo > 0) parts.push({ text: "… ", match: false });
  for (let i = lo; i < hi; i++) {
    parts.push({ text: tokens[i]!.surface, match: isMatch[i]! });
    parts.push({ text: tokens[i]!.punctuationAfter, match: false });
  }
  if (hi < tokens.length) parts.push({ text: " …", match: false });
  return parts;
}

/**
 * Search ONE book. The core both scopes share: `searchAll` is this over
 * every corpus in the registry, `searchBook` is this with a deeper cap.
 *
 * Query terms are normalised with the same function that produces the
 * lexicon's join key, so typing `صلاه` finds `صَلَاةٍ` — a student should not
 * have to know the vowelling of the word they are looking for.
 *
 * Multiple terms are BEST-MATCH, not strict AND: results are the records
 * matching the greatest number of distinct terms. A student typing a
 * half-remembered phrase should get the closest hadith rather than nothing.
 */
async function searchIn(
  corpus: string,
  query: string,
  mode: Mode,
  cap: number,
): Promise<{ hits: Hit[]; terms: string[]; total: number; rootKnown: string | null }> {
  const [index, { postings, roots }] = await Promise.all([
    loadIndexOf(corpus),
    loadSearchOf(corpus),
  ]);

  const order = index.navigation.orderedIds;
  const numberOf = new Map<string, number>();
  for (const [num, id] of Object.entries(index.navigation.numberIndex)) {
    if (!numberOf.has(id)) numberOf.set(id, Number(num));
  }

  const renderHit = async (
    seq: number,
    positions: number[],
    terms: string[],
    matched: number,
  ): Promise<Hit> => {
    const id = order[seq - 1]!;
    const rec = await loadRecordOf(corpus, id, index.buildId);
    let snippet: { text: string; match: boolean }[];
    if (positions.length > 0) {
      const marked = new Set(positions);
      const first = positions[0] ?? 0;
      const lo = Math.max(0, first - SNIPPET_RADIUS);
      const hi = Math.min(rec.tokens.length, first + SNIPPET_RADIUS + 1);
      snippet = [];
      if (lo > 0) snippet.push({ text: "… ", match: false });
      for (let i = lo; i < hi; i++) {
        snippet.push({ text: rec.tokens[i]!.surface, match: marked.has(i) });
        snippet.push({ text: rec.tokens[i]!.punctuationAfter, match: false });
      }
      if (hi < rec.tokens.length) snippet.push({ text: " …", match: false });
    } else {
      snippet = buildSnippet(rec.tokens, terms);
    }
    return {
      corpus,
      seq,
      id,
      number: numberOf.get(id) ?? ownerNumber(seq, order, numberOf),
      kitab: rec.kitab?.titleAr ?? null,
      snippet,
      matched,
    };
  };

  if (mode === "root") {
    const key = rootKey(query.trim());
    const list = key ? roots.get(key) : undefined;
    if (!key || !list) return { hits: [], terms: [key ?? ""], total: 0, rootKnown: null };
    const page = list.slice(0, cap);
    const hits = await Promise.all(
      page.map((p) => renderHit(p.seq, p.positions, [], p.positions.length)),
    );
    return { hits, terms: [key], total: list.length, rootKnown: key };
  }

  const terms = [...new Set(query.trim().split(/\s+/).map(normalise).filter(Boolean))];
  if (terms.length === 0) return { hits: [], terms: [], total: 0, rootKnown: null };
  const rk = rootKey(query.trim());
  const rootKnown = rk && roots.has(rk) ? rk : null;

  const counts = new Map<number, number>();
  for (const t of terms) {
    for (const p of postings.get(t) ?? []) {
      counts.set(p.seq, (counts.get(p.seq) ?? 0) + 1);
    }
  }
  if (counts.size === 0) return { hits: [], terms, total: 0, rootKnown };
  const best = Math.max(...counts.values());
  const ranked = [...counts.entries()]
    .filter(([, n]) => n === best)
    .sort((a, b) => a[0] - b[0]);

  const page = ranked.slice(0, cap);
  const hits = await Promise.all(page.map(([seq]) => renderHit(seq, [], terms, best)));
  return { hits, terms, total: ranked.length, rootKnown };
}

export interface ScopedResult {
  books: BookHits[];
  terms: string[];
  total: number;
  rootAvailable: string | null;
}

/** Single-book search — the "this book" scope. */
export async function searchBook(
  corpus: string,
  query: string,
  mode: Mode,
): Promise<ScopedResult> {
  const [r, corpora] = await Promise.all([
    searchIn(corpus, query, mode, MAX_RESULTS),
    loadCorpora(),
  ]);
  const meta = corpora.find((c) => c.id === corpus);
  return {
    books:
      r.total > 0
        ? [{ corpus, titleAr: meta?.titleAr ?? null, hits: r.hits, total: r.total }]
        : [],
    terms: r.terms,
    total: r.total,
    rootAvailable: mode === "form" ? r.rootKnown : null,
  };
}

/**
 * Search EVERY book — the default scope. The current book leads (the reader
 * asked from inside it) and the rest follow in registry order, each capped
 * so one common word in one long book cannot drown the others; the per-book
 * total says what the cap hid, and each section links to that book's
 * single-book scope for the rest.
 *
 * A book that fails to load is skipped rather than failing the search:
 * eight answers and a console warning beat zero.
 */
export async function searchAll(
  currentCorpus: string,
  query: string,
  mode: Mode,
): Promise<ScopedResult> {
  const corpora = await loadCorpora();
  const ordered = [
    ...corpora.filter((c) => c.id === currentCorpus),
    ...corpora.filter((c) => c.id !== currentCorpus),
  ];
  const settled = await Promise.allSettled(
    ordered.map((c) => searchIn(c.id, query, mode, PER_BOOK)),
  );
  const books: BookHits[] = [];
  let terms: string[] = [];
  let total = 0;
  let rootAvailable: string | null = null;
  settled.forEach((res, i) => {
    if (res.status !== "fulfilled") {
      console.warn(`search: skipping ${ordered[i]!.id}:`, res.reason);
      return;
    }
    const r = res.value;
    if (r.terms.length > 0) terms = r.terms;
    if (mode === "form" && r.rootKnown && !rootAvailable) rootAvailable = r.rootKnown;
    if (r.total === 0) return;
    total += r.total;
    books.push({
      corpus: ordered[i]!.id,
      titleAr: ordered[i]!.titleAr,
      hits: r.hits,
      total: r.total,
    });
  });
  return { books, terms, total, rootAvailable };
}
