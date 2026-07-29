# Phase 3 — token binding report

```
tier                              all tokens       %       matn       %
  1 unique                            63,915   50.3%     59,839   50.2%
  2 aligned                           58,448   46.0%     55,726   46.8%
  3 heuristic (case)                   2,511    2.0%      2,213    1.9%
  4 heuristic (most-frequent)          2,277    1.8%      1,335    1.1%
  5 unbound                               12    0.0%         11    0.0%
  TOTAL                              127,163  100.0%    119,124  100.0%

GATE — Tier 1+2 on matn: 97.0%  (requires >= 90.0%)  PASS
Naive ceiling for comparison: 85.9% (always take the most frequent candidate)

Tier 3 breakdown: L-collocation 2,072, R-collocation 219, case-agreement 125, L-repair 94, R-repair 1

Bukhari retrieval: 2,338 of 2,342 records matched, median coverage 0.959, 4 below 0.35, 0 with no candidate row
Retrieved row corroborated by the record's own (بخاري: N) reference or coverage>=0.8: 2,085/2,220 (93.9%)

## Held-out accuracy of the heuristic tiers

Tier-2 tokens have an independent witness (the vocalised Bukhari word).
Hiding it and re-deriving the answer measures what Tiers 3 and 4 are worth.

  evaluated on 58,448 Tier-2 tokens in matn and zawa'id
  Tier 3 rule fired on          28,035 (48.0%), correct 27,252 = 97.2%   -> error 2.8%
  Tier 3 declined to fire on    30,413 (52.0%) — these fall to Tier 4
  Tier 4 most-frequent fallback 58,448, correct 40,827 = 69.9%   -> error 30.1%

  So the medium/low confidence split is real: the Tier 3 rules are 27 points more accurate than the fallback they replace.

## Cross-check against the workbook's Review sheet

The Review sheet flags 3,349 forms whose vocalisation the WORKBOOK could not
settle from context. They should be scarce where we are confident and dense
where we are guessing. Measured per form, against the base rate:

resolved mostly at                  forms   flagged    rate   vs base
  2 aligned                         2,930     1,613   55.1%     -0.5
  3 heuristic (case)                    2         0    0.0%    -55.5
  4 heuristic (most-frequent)          53        44   83.0%    +27.5
  base rate (all ambiguous forms)    2,985     1,657   55.5%     +0.0

  Flagged forms are enriched +27.5 points in the most-frequent fallback tier and sit at base in the aligned tier, which is the clustering the gate asks for.

  Token-weighted, for completeness — dominated by a few very frequent forms
  and correspondingly uninformative:
    2 aligned                         58,448      50,736   86.8%
    3 heuristic (case)                 2,511       2,412   96.1%
    4 heuristic (most-frequent)        2,277       2,013   88.4%
```
