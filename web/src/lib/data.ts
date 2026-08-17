import type { IndexFile, HadithFile, Layer } from "@/types/contracts";

const ROOT = `${import.meta.env.BASE_URL}data`;

/**
 * Which book is being read.
 *
 * The payload used to live at one path and `index.json` simply WAS al-Tajrid.
 * It is now `data/corpora/{id}/`, with `data/corpora.json` listing what this
 * deployment serves. The current corpus is module state rather than a React
 * context because `loadRecord` and friends are plain functions called from
 * outside the component tree; the URL remains the source of truth and calls
 * `setCorpus` on navigation.
 */
let currentCorpus = "tajrid";
export const corpusBase = () => `${ROOT}/corpora/${currentCorpus}`;
/** Payload root, above any corpus: the shared lexicon lives here. */
export const dataRoot = () => ROOT;
const BASE = corpusBase;

export function getCorpus(): string {
  return currentCorpus;
}

export interface CorpusSummary {
  id: string;
  titleAr: string | null;
  titleEn: string | null;
  author: string | null;
  records: number;
  unit: string;
  hasGlosses: boolean;
}

let registryPromise: Promise<CorpusSummary[]> | null = null;

/** The only file fetched before we know which book we are showing. */
export function loadCorpora(): Promise<CorpusSummary[]> {
  registryPromise ??= fetch(`${ROOT}/corpora.json`, { cache: "no-cache" })
    .then((r) => {
      if (!r.ok) throw new Error(`corpora.json: HTTP ${r.status}`);
      return r.json();
    })
    .then((d) => d.corpora as CorpusSummary[]);
  return registryPromise;
}

/**
 * The index is loaded once and held. Everything else is versioned by its
 * buildId so the browser can cache it permanently — see pipeline/build.py.
 */
let indexPromise: Promise<IndexFile> | null = null;

export function loadIndex(): Promise<IndexFile> {
  // `cache: "no-cache"` forces revalidation with the server on every load.
  //
  // index.json carries the SHARD COUNTS, and those counts are derived from the
  // payload size, so they change when the content does — the surface set went
  // from 64 shards to 32 the moment the statistics moved into their own files.
  // A browser holding a stale index then computes `hash % 64`, asks for shard
  // 39, and gets a 404 for half the words in the book.
  //
  // `web/public/_headers` already says this file must revalidate, but GitHub
  // Pages ignores `_headers` and applies its own cache. The header is advice to
  // hosts that read it; this is the part that does not depend on the host.
  indexPromise ??= fetch(`${BASE()}/index.json`, { cache: "no-cache" }).then((r) => {
    if (!r.ok) throw new Error(`index.json: HTTP ${r.status}`);
    return r.json() as Promise<IndexFile>;
  });
  return indexPromise;
}

/**
 * Discard the cached index so the next `loadIndex` refetches it.
 *
 * Belt and braces for the failure above: a CDN that ignores `no-cache` would
 * still serve a stale index, and a stale index cannot be detected from its own
 * contents — only from a shard that turns out not to exist.
 */
export function invalidateIndex(): void {
  indexPromise = null;
}

// ---------------------------------------------------------------------------
// EXPLICIT-CORPUS loaders, for the one consumer that reads several books at
// once: cross-corpus search. The globals above answer "the book the reader
// is in" and their caches turn over on setCorpus; these answer "that book,
// whichever the reader is in", cache per corpus, and never touch the
// global. Search resolving one book's postings against another book's
// record order is the bug class this split exists to make impossible.
// ---------------------------------------------------------------------------

const indexOfCache = new Map<string, Promise<IndexFile>>();

export function loadIndexOf(corpus: string): Promise<IndexFile> {
  let p = indexOfCache.get(corpus);
  if (!p) {
    p = fetch(`${ROOT}/corpora/${corpus}/index.json`, { cache: "no-cache" }).then((r) => {
      if (!r.ok) throw new Error(`${corpus}/index.json: HTTP ${r.status}`);
      return r.json() as Promise<IndexFile>;
    });
    indexOfCache.set(corpus, p);
  }
  return p;
}

const recordOfCache = new Map<string, Promise<HadithFile>>();

export function loadRecordOf(corpus: string, id: string, buildId: string): Promise<HadithFile> {
  const key = `${corpus}/${id}`;
  let p = recordOfCache.get(key);
  if (!p) {
    p = fetch(`${ROOT}/corpora/${corpus}/hadith/${id}.json?v=${buildId}`).then((r) => {
      if (!r.ok) throw new Error(`${key}: HTTP ${r.status}`);
      return r.json() as Promise<HadithFile>;
    });
    recordOfCache.set(key, p);
  }
  return p;
}

const hadithCache = new Map<string, Promise<HadithFile>>();

export function setCorpus(id: string): void {
  if (id === currentCorpus) return;
  currentCorpus = id;
  // Everything cached belongs to the previous book. Records and the index are
  // per-corpus; keeping them would silently show one book's hadith under
  // another's navigation.
  indexPromise = null;
  hadithCache.clear();
  // Deliberately NOT clearing the shared surface shards: they are the same
  // bytes for every corpus, and dropping them would make switching books cost
  // a re-download of the lexicon it already has.
}



export function loadRecord(id: string, buildId: string): Promise<HadithFile> {
  let p = hadithCache.get(id);
  if (!p) {
    p = fetch(`${BASE()}/hadith/${id}.json?v=${buildId}`).then((r) => {
      if (!r.ok) throw new Error(`${id}: HTTP ${r.status}`);
      return r.json() as Promise<HadithFile>;
    });
    hadithCache.set(id, p);
  }
  return p;
}

/** Record IDs are `{layer}-{seq}`, so the layer is readable without a lookup. */
export function layerOf(id: string): Layer {
  return id.slice(0, id.lastIndexOf("-")) as Layer;
}

/**
 * What a single screen shows.
 *
 * A zawa'id addition is an unnumbered hadith that al-Diya' al-Daghistani
 * inserted after a numbered one, and it only makes sense next to the hadith it
 * supplements — so the page for hadith N carries any zawa'id records that
 * immediately follow it. This is also why `/hadith/:number` can address the
 * whole corpus even though 88 records have no number of their own.
 */
export interface Page {
  main: HadithFile;
  additions: HadithFile[];
}

/**
 * Neighbouring hadith numbers, derived from the index alone.
 *
 * Deliberately NOT taken from the loaded record: the index is in memory from
 * boot, so the controls can render and the keyboard can fire the instant a URL
 * is known, without waiting for a fetch. Reading them off the record instead
 * meant keypresses were silently dropped during a load, and the footer popped
 * into existence when the record arrived — a layout shift on every navigation.
 */
export function neighbours(
  index: IndexFile,
  number: number,
): { prev: number | null; next: number | null } {
  const numbers = numberedList(index);
  const at = numbers.indexOf(number);
  if (at === -1) return { prev: null, next: null };
  return {
    prev: at > 0 ? (numbers[at - 1] ?? null) : null,
    next: at < numbers.length - 1 ? (numbers[at + 1] ?? null) : null,
  };
}

export async function loadPage(number: number): Promise<Page | null> {
  const index = await loadIndex();
  const id = index.navigation.numberIndex[String(number)];
  if (!id) return null;

  const order = index.navigation.orderedIds;
  const pos = order.indexOf(id);
  const main = await loadRecord(id, index.buildId);

  const additions: HadithFile[] = [];
  for (let i = pos + 1; i < order.length; i++) {
    const nextId = order[i];
    // The ASIDE LAYER, whatever this corpus calls it. Hardcoded to al-Tajrid's
    // `zawaid`, it silently dropped every addition in a book that names the
    // layer differently: Bulugh's 591 takhrij notes — who narrated each hadith
    // and how it was graded, which is much of what that book is for — were
    // built, shipped, and never shown.
    if (!nextId || layerOf(nextId) !== (index.corpus.asideLayer ?? "zawaid")) break;
    additions.push(await loadRecord(nextId, index.buildId));
  }

  return { main, additions };
}

let numbersCache: number[] | null = null;

/** Every display number that resolves, ascending. */
export function numberedList(index: IndexFile): number[] {
  numbersCache ??= Object.keys(index.navigation.numberIndex)
    .map(Number)
    .sort((a, b) => a - b);
  return numbersCache;
}

/** The first hadith number at or after a given record, for the kitab browser. */
export async function numberAtRecord(recordId: string): Promise<number | null> {
  const index = await loadIndex();
  const order = index.navigation.orderedIds;
  const byId = new Map<string, number>();
  for (const [num, id] of Object.entries(index.navigation.numberIndex)) {
    if (!byId.has(id)) byId.set(id, Number(num));
  }
  for (let i = order.indexOf(recordId); i < order.length && i >= 0; i++) {
    const id = order[i];
    if (id && byId.has(id)) return byId.get(id)!;
  }
  return null;
}
