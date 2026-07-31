# CAMeL (calima-msa-r13) vs qalsadi+arramooz — roots

Agreement is NOT accuracy; the two stacks share Buckwalter-lexicon
ancestry (see bakeoff_camel.py header). The decider is the gold
sample. This report maps where they differ and what Lane says there.

| forms analysed | 27,481 |
|---|--:|
| CAMeL covers | 25,931 (94.4%) |
| CAMeL unique after diacritic filter | 24,492 |
| masked weak radicals | 11,455, resolved via arramooz 8,199 |
| both have a root | 23,540 |
| **agree** | **21,823 (92.7%)** |
| disagree | 1,717 |
| only ours has a root | 713 |
| only CAMeL has a root | 2,391 |
| neither | 837 |

## The disagreements, adjudicated by Lane existence

| Lane has | count |
|---|--:|
| only our root | 321 |
| only CAMeL's | 818 |
| both (Lane cannot decide) | 313 |
| neither | 265 |

## Our basis where they disagree

| basis | count |
|---|--:|
| unanimous | 1,328 |
| vocalised | 163 |
| unresolved | 104 |
| majority | 66 |
| lane | 56 |

Disagreements: `pipeline/build/bakeoff/disagreements.json` — keyed by
vocalised form so gold verdicts join directly when they exist.