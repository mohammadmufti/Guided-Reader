import type { IndexFile } from "@/types/contracts";
import { loadIndex, loadRecord, layerOf } from "@/lib/data";
import { normalise } from "@/lib/normalise";

const BASE = `${import.meta.env.BASE_URL}data`;

interface SearchFile {
  buildId: string;
  postings: Record<string, number[]>;
}

let indexPromise: Promise<Map<string, number[]>> | null = null;

/**
 * The search index is fetched only when someone actually searches.
 *
 * 150 KB brotli for 18,578 keys — small enough not to shard, large enough that
 * it has no business in the cold load. Postings are delta-encoded ascending
 * record sequence numbers; they are expanded once, here, and kept.
 */
export async function loadSearchIndex(): Promise<Map<string, number[]>> {
  if (!indexPromise) {
    indexPromise = (async () => {
      const index = await loadIndex();
      const res = await fetch(`${BASE}/search.json?v=${index.buildId}`);
      if (!res.ok) throw new Error(`search.json: HTTP ${res.status}`);
      const file = (await res.json()) as SearchFile;
      const out = new Map<string, number[]>();
      for (const [key, deltas] of Object.entries(file.postings)) {
        const seqs: number[] = [];
        let acc = 0;
        for (const d of deltas) {
          acc += d;
          seqs.push(acc);
        }
        out.set(key, seqs);
      }
      return out;
    })();
  }
  return indexPromise;
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
export async function search(
  query: string,
  index: IndexFile,
): Promise<{ hits: Hit[]; terms: string[]; total: number }> {
  const terms = [...new Set(query.trim().split(/\s+/).map(normalise).filter(Boolean))];
  if (terms.length === 0) return { hits: [], terms: [], total: 0 };

  const postings = await loadSearchIndex();
  const lists = terms.map((t) => postings.get(t) ?? []);
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
        number: numberOf.get(id) ?? null,
        kitab: rec.kitab?.titleAr ?? null,
        snippet: buildSnippet(rec.tokens, terms),
        matched: best,
      };
    }),
  );
  void layerOf;
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
