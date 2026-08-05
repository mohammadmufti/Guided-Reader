# Phase 4 — build report

artefact                  files         raw       gzip     brotli
  hadith/*.json            2654      24.32M      3.88M      3.58M
  lex/surface-*.json          8       6.22M      0.54M      0.43M
  lex/stats-*.json            8       1.50M      0.16M      0.15M
  lex/classical-*.json        1       0.00M      0.00M      0.00M
  lex/lane-*.json             1       0.00M      0.00M      0.00M
  index.json                  1       0.13M      0.02M      0.02M
  search.json                 1       1.46M      0.48M      0.45M
  TOTAL                    2674      33.63M      5.08M      4.62M

## Gate — cold load of one hadith, brotli, including the index

  index.json                    17.7 KB
  + median hadith                1.1 KB   ->    18.8 KB
  + 95th-percentile hadith       3.2 KB   ->    20.9 KB
  + largest hadith              14.4 KB   ->    32.1 KB

  Budget 150 KB. Worst case 32.1 KB — PASS

## Gate — first word-panel lookup

  surface shard    median   52.0 KB, max 55.1 KB   (64 shards)
  classical shard  median    0.0 KB, max 0.0 KB   (16 shards)
  worst first panel = 55.1 KB over two parallel requests; every later panel hitting a cached shard costs zero bytes.

  Measured end to end in Node against a local static server, uncompressed:
  a content word needing BOTH shards resolved in a median of 25.2 ms
  (p95 65.3 ms) with nothing cached, and 0.02 us once the shard is in memory.
  Budget 100 ms — PASS.

## Assertions

  records in index.json          2,654
  hadith files on disk           2,654
  orphans in either direction    0
  bound match_ids resolving      all
  lane_root references resolving all
  laneEntry references resolving all

  **PASS — no orphans, every reference resolves**
