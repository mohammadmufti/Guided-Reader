# Phase 4 — build report

artefact                  files         raw       gzip     brotli
  hadith/*.json            2550      21.22M      3.61M      2.91M
  lex/surface-*.json         64      15.49M      2.11M      1.50M
  lex/classical-*.json        4       0.63M      0.18M      0.15M
  lex/lane-*.json           512      39.86M      8.36M      7.03M
  index.json                  1       0.11M      0.03M      0.01M
  search.json                 1       0.57M      0.18M      0.15M
  TOTAL                    3132      77.87M     14.46M     11.75M

## Gate — cold load of one hadith, brotli, including the index

  index.json                    12.3 KB
  + median hadith                0.9 KB   ->    13.2 KB
  + 95th-percentile hadith       2.2 KB   ->    14.5 KB
  + largest hadith              17.7 KB   ->    30.0 KB

  Budget 150 KB. Worst case 30.0 KB — PASS

## Gate — first word-panel lookup

  surface shard    median   22.7 KB, max 26.8 KB   (64 shards)
  classical shard  median   36.2 KB, max 37.5 KB   (16 shards)
  worst first panel = 64.3 KB over two parallel requests; every later panel hitting a cached shard costs zero bytes.

  Measured end to end in Node against a local static server, uncompressed:
  a content word needing BOTH shards resolved in a median of 25.2 ms
  (p95 65.3 ms) with nothing cached, and 0.02 us once the shard is in memory.
  Budget 100 ms — PASS.

## Assertions

  records in index.json          2,550
  hadith files on disk           2,550
  orphans in either direction    0
  bound match_ids resolving      all
  lane_root references resolving all
  laneEntry references resolving all

  **PASS — no orphans, every reference resolves**
