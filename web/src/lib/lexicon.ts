import { loadIndex, invalidateIndex } from "@/lib/data";

import type {
  IndexFile,
  PanelEntry,
  ClassicalEntry,
  CorpusStats,
  LaneRoot,
  LaneEntry,
} from "@/types/contracts";

// Per-corpus payload root. Shared with data.ts so a corpus switch moves
// every fetch at once; a half-switched client would pair one book's
// lexicon shards with another book's records.
import { corpusBase, dataRoot } from "./data";

/** Cache key for the shared lexicon: its own content hash, not a buildId. */
function lexVer(index: IndexFile): string {
  return index.shards.lexiconVersion ? `?v=${index.shards.lexiconVersion}` : "";
}

/**
 * 32-bit FNV-1a over UTF-8, byte for byte the same function as `fnv1a` in
 * pipeline/build.py. A match_id is routed to its shard without any lookup
 * table, so the index does not have to carry 22,464 entries. If either copy is
 * changed the other must change with it — the build asserts that every bound
 * match_id resolves in the shard it hashes to, which is what would catch a drift.
 */
export function fnv1a(text: string): number {
  let h = 0x811c9dc5;
  for (const byte of new TextEncoder().encode(text)) {
    h ^= byte;
    h = Math.imul(h, 0x01000193) >>> 0;
  }
  return h >>> 0;
}

// Shard filenames are three digits: counts are derived from a byte budget and
// the Lane set currently needs 512.
const pad = (n: number) => String(n).padStart(3, "0");

const surfaceShards = new Map<number, Promise<Record<string, PanelEntry>>>();
const statsShards = new Map<number, Promise<Record<string, CorpusStats>>>();
const classicalShards = new Map<number, Promise<Record<string, ClassicalEntry>>>();
const laneShards = new Map<number, Promise<Record<string, LaneRoot>>>();

function fetchJson<T>(url: string): Promise<T> {
  return fetch(url).then((r) => {
    if (!r.ok) throw new Error(`${url.split("/").pop()}: HTTP ${r.status}`);
    return r.json() as Promise<T>;
  });
}

export interface PanelData {
  entry: PanelEntry;
  /** How the form behaves in THIS corpus. Shipped separately so `entry` can be shared. */
  stats: CorpusStats | null;
  classical: ClassicalEntry | null;
  /** Every Lane entry under this root, or null when the root has none. */
  lane: LaneRoot | null;
  /** The entry for THIS lemma specifically, when one was matched at build time. */
  laneEntry: LaneEntry | null;
}

/**
 * Everything the panel needs for one word.
 *
 * Two shards at most, fetched in parallel and then cached for the session:
 * the surface shard keyed by search_key and, when the word has a root, the
 * classical shard keyed by lane_root. Measured cold at 25 ms median / 65 ms
 * p95; once a shard is in memory the lookup is a map read.
 */
/**
 * A 404 on a shard means the index we routed with is out of date — the counts
 * changed under us. Drop it, fetch a fresh one, and try again exactly once.
 * Without this the reader is stuck until a cache expires, with no way to tell
 * from inside the page what is wrong.
 */
async function withFreshIndex<T>(
  index: IndexFile,
  run: (index: IndexFile) => Promise<T>,
): Promise<T> {
  try {
    return await run(index);
  } catch (error) {
    if (!(error instanceof Error) || !error.message.includes("404")) throw error;
    invalidateIndex();
    surfaceShards.clear();
    statsShards.clear();
    classicalShards.clear();
    laneShards.clear();
    return run(await loadIndex());
  }
}

export async function loadPanel(matchId: string, index: IndexFile): Promise<PanelData> {
  return withFreshIndex(index, (fresh) => loadPanelOnce(matchId, fresh));
}

async function loadPanelOnce(
  matchId: string,
  index: IndexFile,
): Promise<PanelData> {
  const searchKey = matchId.slice(0, matchId.lastIndexOf("#"));

  // TWO MODULI, deliberately. What a word IS lives in one shared set across
  // every corpus, because `match_id` is derived from the form and an entry is
  // therefore identical wherever it occurs. What a word DOES here — frequency,
  // rank, which layers it appears in — is per corpus. The two sets are sized
  // independently against the same byte budget, so they do not share a shard
  // count and must not share one here.
  const shared = index.shards.sharedSurface ?? index.shards.surface;
  const su = fnv1a(searchKey) % shared;
  let shard = surfaceShards.get(su);
  if (!shard) {
    shard = fetchJson<Record<string, PanelEntry>>(
      // No corpus in the path — a shared entry does not change when one
      // corpus is rebuilt, and cache-busting per corpus would throw away a
      // hit the reader has already paid for.
      //
      // But it DOES carry `lexiconVersion`, a hash of the shared set. Without
      // it the URL never changed, so a reader who had visited before kept the
      // old entries indefinitely: the text updated and the word panel did not.
      `${dataRoot()}/lexicon/surface-${pad(su)}.json${lexVer(index)}`,
    );
    surfaceShards.set(su, shard);
  }
  // Statistics live in a parallel shard set on the same routing, so this is one
  // extra request, in flight alongside the first rather than after it. The
  // split is what lets a lexical entry be identical across corpora.
  const s = fnv1a(searchKey) % index.shards.surface;
  let statsShard = statsShards.get(s);
  if (!statsShard) {
    statsShard = fetchJson<Record<string, CorpusStats>>(
      `${corpusBase()}/lex/stats-${pad(s)}.json?v=${index.buildId}`,
    );
    statsShards.set(s, statsShard);
  }

  const [forms, statsMap] = await Promise.all([shard, statsShard]);
  const entry = forms[matchId];
  if (!entry) throw new Error(`${matchId} is not in surface shard ${s}`);
  const stats = statsMap[matchId] ?? null;

  if (!entry.lane_root)
    return { entry, stats, classical: null, lane: null, laneEntry: null };

  // Classical summary and Lane entries are separate shard sets — the summary is
  // tiny and read for every rooted word, the entries are large and only worth
  // fetching for the root actually being looked at. Both in parallel.
  // Shared moduli when share.py has run, the corpus's own otherwise. Lane is
  // a dictionary: the same word must resolve to the same entry whichever book
  // it is read in, and before this only al-Tajrid shipped the shards at all.
  const c = fnv1a(entry.lane_root) % (index.shards.sharedClassical ?? index.shards.classical);
  const l = fnv1a(entry.lane_root) % (index.shards.sharedLane ?? index.shards.lane);
  let cShard = classicalShards.get(c);
  if (!cShard) {
    cShard = fetchJson<Record<string, ClassicalEntry>>(
      `${dataRoot()}/lexicon/classical-${pad(c)}.json${lexVer(index)}`,
    );
    classicalShards.set(c, cShard);
  }
  let lShard = laneShards.get(l);
  if (!lShard) {
    lShard = fetchJson<Record<string, LaneRoot>>(
      `${dataRoot()}/lexicon/lane-${pad(l)}.json${lexVer(index)}`,
    );
    laneShards.set(l, lShard);
  }
  const [classicalMap, laneMap] = await Promise.all([cShard, lShard]);
  const lane = laneMap[entry.lane_root] ?? null;
  const laneEntry =
    (entry.laneEntry && lane?.entries.find((e) => e.nodeid === entry.laneEntry)) || null;
  return { entry, stats, classical: classicalMap[entry.lane_root] ?? null, lane, laneEntry };
}
