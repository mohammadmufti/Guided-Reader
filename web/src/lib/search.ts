import type { IndexFile } from "@/types/contracts";
import { loadIndex, loadRecord } from "@/lib/data";
import { normalise, rootKey } from "@/lib/normalise";

// Per-corpus payload root. Shared with data.ts so a corpus switch moves
// every fetch at once; a half-switched client would pair one book's
// lexicon shards with another book's records.
import { corpusBase, getCorpus } from "./data";

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

let indexPromise: Promise<Map<string, Posting[]>> | null = null;
let rootIndex: Map<string, Posting[]> = new Map();
// WHOSE index is cached. data.ts resets its own caches on a corpus switch
// but cannot reach these, and a stale index is worse than a stale record:
// postings are record SEQUENCE numbers, so one book's postings resolved
// against another book's ordered ids return real-looking hits pointing at
// unrelated hadith. Search after switching from al-Tajrid to Bulugh was
// exactly that. Checked here, at the one entry point, rather than wired
// into setCorpus — an import from data.ts back into this module is a cycle.
let indexCorpus: string | null = null;

/** Roots are loaded with the form index; call after `loadSearchIndex`. */
export function knownRoot(query: string): string | null {
  const key = rootKey(query);
  return key && rootIndex.has(key) ? key : null;
}

/**
 * The search index is fetched only when someone actually searches.
 *
 * 150 KB brotli for 18,578 keys — small enough not to shard, large enough that
 * it has no business in the cold load. Postings are delta-encoded ascending
 * record sequence numbers; they are expanded once, here, and kept.
 */
export async function loadSearchIndex(): Promise<Map<string, Posting[]>> {
  if (indexCorpus !== getCorpus()) {
    indexPromise = null;
    rootIndex = new Map();
    indexCorpus = getCorpus();
  }
  if (!indexPromise) {
    indexPromise = (async () => {
      const index = await loadIndex();
      const res = await fetch(`${corpusBase()}/search.json?v=${index.buildId}`);
      if (!res.ok) throw new Error(`search.json: HTTP ${res.status}`);
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
      rootIndex = expand(file.roots ?? {});
      return expand(file.postings);
    })();
  }
  return indexPromise;
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
 * Every other place a spelling occurs, with context.
 *
 * Deliberately NOT fetched with the panel. The index is 310 KB and most panels
 * are opened to read a gloss, so it loads only when a reader asks for it — the
 * count itself is already on the entry as `doc_freq`, so the offer costs
 * nothing until taken.
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
  const searchKey = matchId.slice(0, matchId.lastIndexOf("#"));
  const postings = await loadSearchIndex();
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
    const rec = await loadRecord(c.id, index.buildId);
    if (rec.tokens[c.index]?.matchId === matchId) flat.push(c);
    if (flat.length >= MAX_OCCURRENCES) break;
  }

  const page = flat;
  const shown = await Promise.all(
    page.map(async ({ id, index: i, seq }) => {
      const rec = await loadRecord(id, index.buildId);
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
  seq: number;
  id: string;
  number: number | null;
  kitab: string | null;
  snippet: { text: string; match: boolean }[];
  matched: number;
}

const MAX_RESULTS = 40;
const SNIPPET_RADIUS = 7;

/**
 * Search the corpus.
 *
 * Query terms are normalised with the same function that produces the lexicon's
 * join key, so typing `صلاه` finds `صَلَاةٍ` — a student should not have to know
 * the vowelling of the word they are looking up, which is rather the point.
 *
 * Multiple terms are BEST-MATCH, not strict AND: results are the records
 * matching the greatest number of distinct terms. A student typing a
 * half-remembered phrase should get the closest hadith rather than nothing,
 * and a strict AND on four terms usually returns nothing.
 */
export type Mode = "form" | "root";

/**
 * Search by ROOT rather than by written form.
 *
 * Form search is exact: `كتب` finds neither `مكتوب` nor `يكتب`. For a student
 * asking what else comes from a root that is the wrong question answered
 * precisely. 51.9% of tokens carry a root, so this covers the content words and
 * leaves particles to form search, which is the right split.
 */
export async function searchByRoot(
  query: string,
  index: IndexFile,
): Promise<{ hits: Hit[]; terms: string[]; total: number }> {
  await loadSearchIndex();
  const key = rootKey(query.trim());
  const list = rootIndex.get(key);
  if (!key || !list) return { hits: [], terms: [key], total: 0 };

  const order = index.navigation.orderedIds;
  const numberOf = new Map<string, number>();
  for (const [num, id] of Object.entries(index.navigation.numberIndex)) {
    if (!numberOf.has(id)) numberOf.set(id, Number(num));
  }
  const page = list.slice(0, MAX_RESULTS);
  const hits = await Promise.all(
    page.map(async (p) => {
      const id = order[p.seq - 1]!;
      const rec = await loadRecord(id, index.buildId);
      const marked = new Set(p.positions);
      const first = p.positions[0] ?? 0;
      const lo = Math.max(0, first - SNIPPET_RADIUS);
      const hi = Math.min(rec.tokens.length, first + SNIPPET_RADIUS + 1);
      const parts: { text: string; match: boolean }[] = [];
      if (lo > 0) parts.push({ text: "… ", match: false });
      for (let i = lo; i < hi; i++) {
        parts.push({ text: rec.tokens[i]!.surface, match: marked.has(i) });
        parts.push({ text: rec.tokens[i]!.punctuationAfter, match: false });
      }
      if (hi < rec.tokens.length) parts.push({ text: " …", match: false });
      return {
        seq: p.seq,
        id,
        number: numberOf.get(id) ?? ownerNumber(p.seq, order, numberOf),
        kitab: rec.kitab?.titleAr ?? null,
        snippet: parts,
        matched: p.positions.length,
      };
    }),
  );
  return { hits, terms: [key], total: list.length };
}

/**
 * The numbered record a sequence position belongs to — itself when numbered,
 * else the numbered record it sits under (a heading or an addition), the
 * same walk loadOccurrences uses. A search hit on a bab title used to link
 * to /read/null.
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

export async function search(
  query: string,
  index: IndexFile,
): Promise<{ hits: Hit[]; terms: string[]; total: number }> {
  const terms = [...new Set(query.trim().split(/\s+/).map(normalise).filter(Boolean))];
  if (terms.length === 0) return { hits: [], terms: [], total: 0 };

  const postings = await loadSearchIndex();
  const lists = terms.map((t) => (postings.get(t) ?? []).map((p) => p.seq));
  if (lists.some((l) => l.length === 0)) {
    // One term matches nothing, so nothing can match all of them.
    const present = terms.filter((t) => postings.has(t));
    if (present.length === 0) return { hits: [], terms, total: 0 };
  }

  const counts = new Map<number, number>();
  lists.forEach((list) => {
    for (const seq of list) counts.set(seq, (counts.get(seq) ?? 0) + 1);
  });
  const best = Math.max(...counts.values());
  const ranked = [...counts.entries()]
    .filter(([, n]) => n === best)
    .sort((a, b) => a[0] - b[0]);

  const order = index.navigation.orderedIds;
  const numberOf = new Map<string, number>();
  for (const [num, id] of Object.entries(index.navigation.numberIndex)) {
    if (!numberOf.has(id)) numberOf.set(id, Number(num));
  }

  const page = ranked.slice(0, MAX_RESULTS);
  const hits = await Promise.all(
    page.map(async ([seq]) => {
      const id = order[seq - 1]!;
      const rec = await loadRecord(id, index.buildId);
      return {
        seq,
        id,
        number: numberOf.get(id) ?? ownerNumber(seq, order, numberOf),
        kitab: rec.kitab?.titleAr ?? null,
        snippet: buildSnippet(rec.tokens, terms),
        matched: best,
      };
    }),
  );
  return { hits, terms, total: ranked.length };
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
