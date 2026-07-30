import type {
  IndexFile,
  PanelEntry,
  ClassicalEntry,
  CorpusStats,
  LaneRoot,
  LaneEntry,
} from "@/types/contracts";

const BASE = `${import.meta.env.BASE_URL}data`;

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
export async function loadPanel(
  matchId: string,
  index: IndexFile,
): Promise<PanelData> {
  const searchKey = matchId.slice(0, matchId.lastIndexOf("#"));
  const s = fnv1a(searchKey) % index.shards.surface;
  let shard = surfaceShards.get(s);
  if (!shard) {
    shard = fetchJson<Record<string, PanelEntry>>(
      `${BASE}/lex/surface-${pad(s)}.json?v=${index.buildId}`,
    );
    surfaceShards.set(s, shard);
  }
  // Statistics live in a parallel shard set on the same routing, so this is one
  // extra request, in flight alongside the first rather than after it. The
  // split is what lets a lexical entry be identical across corpora.
  let statsShard = statsShards.get(s);
  if (!statsShard) {
    statsShard = fetchJson<Record<string, CorpusStats>>(
      `${BASE}/lex/stats-${pad(s)}.json?v=${index.buildId}`,
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
  const c = fnv1a(entry.lane_root) % index.shards.classical;
  const l = fnv1a(entry.lane_root) % index.shards.lane;
  let cShard = classicalShards.get(c);
  if (!cShard) {
    cShard = fetchJson<Record<string, ClassicalEntry>>(
      `${BASE}/lex/classical-${pad(c)}.json?v=${index.buildId}`,
    );
    classicalShards.set(c, cShard);
  }
  let lShard = laneShards.get(l);
  if (!lShard) {
    lShard = fetchJson<Record<string, LaneRoot>>(
      `${BASE}/lex/lane-${pad(l)}.json?v=${index.buildId}`,
    );
    laneShards.set(l, lShard);
  }
  const [classicalMap, laneMap] = await Promise.all([cShard, lShard]);
  const lane = laneMap[entry.lane_root] ?? null;
  const laneEntry =
    (entry.laneEntry && lane?.entries.find((e) => e.nodeid === entry.laneEntry)) || null;
  return { entry, stats, classical: classicalMap[entry.lane_root] ?? null, lane, laneEntry };
}
