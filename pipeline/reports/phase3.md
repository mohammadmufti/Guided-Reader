# Phase 3 — token binding report

```
tier                              all tokens       %       matn       %
  0 source-vowelled                        0    0.0%          0    0.0%
  1 unique                            59,569   46.8%     55,745   46.8%
  2 aligned                           62,951   49.5%     59,987   50.4%
  3 heuristic (case)                   2,714    2.1%      2,402    2.0%
  4 heuristic (most-frequent)          1,917    1.5%        979    0.8%
  5 unbound                               12    0.0%         11    0.0%
  TOTAL                              127,163  100.0%    119,124  100.0%

GATE — Tier 1+2 on matn: 97.2%  (requires >= 90.0%)  PASS
Naive ceiling for comparison: 85.9% (always take the most frequent candidate)

Tier 3 breakdown: L-collocation 2,108, Tier 1 unopposed but unwitnessed 1,354, witness-corrected Tier 1 540, R-collocation 221, syntax-override (ibn) 221, L-repair 94, case-agreement 69, R-repair 1, hand corrections applied 0, Tier 0 from source vowelling 0

Tiers unavailable to this corpus (NOT measured as zero):
  Tier 0 0 source-vowelled            needs source_vocalisation

Morphology on bound matn tokens (root drives the 'other forms of this root' navigation):
  lemma      118,653 / 119,113   99.6%
  root        61,214 / 119,113   51.4%
  pos        118,653 / 119,113   99.6%
  Source: DONORS ONLY — no analyses.json was present.

Gloss enrichment from sibling corpora (match_id is derived from the form, so an entry is shared):
  from glossary: classical_keywords 18,226, din_31635 22,464, divergence 22,464, domain 2,539, gloss_msa 21,028, lane_root 18,226, lemma 22,464, lemma_din 22,458, literal_sense 2,539, morph_confidence 22,464, pos_agreement 22,464, root 18,894, technical_sense 2,539

Source vocalisation: none — every vowel below is inferred.

Witness retrieval: 2,338 of 2,342 records matched, median coverage 0.959, 4 below 0.35, 0 with no candidate row
Retrieved row corroborated by the record's own (بخاري: N) reference or coverage>=0.8: 2,085/2,220 (93.9%)

## Held-out accuracy of the heuristic tiers

Tier-2 tokens have an independent witness (the vocalised parent edition).
Hiding it and re-deriving the answer measures what Tiers 3 and 4 are worth.

  evaluated on 62,951 Tier-2 tokens in matn and zawa'id
  Tier 3 rule fired on          31,500 (50.0%), correct 30,693 = 97.4%   -> error 2.6%
  Tier 3 declined to fire on    31,451 (50.0%) — these fall to Tier 4
  Tier 4 most-frequent fallback 62,951, correct 45,769 = 72.7%   -> error 27.3%

  So the medium/low confidence split is real: the Tier 3 rules are 25 points more accurate than the fallback they replace.

## Cross-check against the workbook's Review sheet

The Review sheet flags 3,349 forms whose vocalisation the WORKBOOK could not
settle from context. They should be scarce where we are confident and dense
where we are guessing. Measured per form, against the base rate:

resolved mostly at                  forms   flagged    rate   vs base
  2 aligned                         3,043     1,721   56.6%     -5.1
  3 heuristic (case)                    1         0    0.0%    -61.7
  4 heuristic (most-frequent)          37        28   75.7%    +14.0
  base rate (all ambiguous forms)    3,503     2,161   61.7%     +0.0

  Flagged forms are enriched +14.0 points in the most-frequent fallback tier and sit at base in the aligned tier, which is the clustering the gate asks for.

  Token-weighted, for completeness — dominated by a few very frequent forms
  and correspondingly uninformative:
    2 aligned                         62,951      51,999   82.6%
    3 heuristic (case)                 2,714       2,575   94.9%
    4 heuristic (most-frequent)        1,917       1,672   87.2%
```
