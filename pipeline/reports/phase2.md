# Phase 2 — lexicon extraction report

Normalisation reproduces **22,464/22,464** `search_key` values exactly.

## Packaging note for Phase 4

`lexicon.json` is **50.2 MB raw / 11.8 MB gzipped**, against Phase 4's ~2 MB shard threshold and its 150 KB cold-load budget. The bulk is not irreducible.

The classical apparatus is a function of `lane_root`: **1,829 distinct roots, 0 with conflicting payloads, 0 forms carrying classical material without a root.** Because §5.2 asks for all 31 Surface columns, it is currently inlined once per surface form — **13.4 MB** where a map keyed by `lane_root` would take **1.4 MB**, a **9.8x** reduction. Surface entries already carry `lane_root`, so the pointer needed to normalise this exists.

`kwic` is another ~2 MB: it is first-occurrence context, useful for binding verification in Phase 3 and of no use to the reading pane.

## Five entries round-tripped

### particle — `من#1` NOT FOUND

### proper noun — `الله#1` NOT FOUND

### curated technical term — `صلاه#1` NOT FOUND

### root-less form — `عليه#603067`

| field | value |
|---|---|
| `rank` | 3 |
| `vocalized` | عَلَيْهِ |
| `din_31635` | ʿalayhi |
| `unvocalized` | عليه |
| `freq` | 3698 |
| `pct` | 2.9071 |
| `cum_pct` | 9.876 |
| `doc_freq` | 2224 |
| `pos` | particle |
| `lemma` | عَلَى |
| `lemma_din` | ʿalā |
| `root` | *(null)* |
| `voc_source` | aligned:3676,lexicon_unique:22 |
| `morph_confidence` | exact_with_case |
| `pos_agreement` | agree |
| `layers` | matn:3509,zawaid:178,frontmatter:7,heading_bab:4 |
| `first_record` | frontmatter-00001 |
| `kwic` | فِيهِ ذَكَرَ النَّبِيُّ صَلَّى اللَّهُ «عَلَيْهِ» وَسَلَّمَ فَلَا أَذْكُرَهُ كحكاية مَشْيُ |
| `search_key` | عليه |
| `gloss_msa` | ___ + on;above + it/him |
| `lane_root` | *(null)* |
| `classical_keywords` | *(null)* |
| `classical_sense_sample` | *(null)* |
| `classical_senses_more` | *(null)* |
| `lane_entry_count` | *(null)* |
| `literal_sense` | *(null)* |
| `technical_sense` | *(null)* |
| `domain` | *(null)* |
| `divergence` | not_applicable |
| `overlap_score` | 0.0 |
| `match_id` | عليه#603067 |
| `workbookMatchId` | عليه#1 |

Homographs on key `عليه`: عليه#603067 (freq 3698)

### hapax — `التجريد#6fc1d3`

| field | value |
|---|---|
| `rank` | 8009 |
| `vocalized` | التجريد |
| `din_31635` | al-tǧryd |
| `unvocalized` | التجريد |
| `freq` | 1 |
| `pct` | 0.0008 |
| `cum_pct` | 88.637 |
| `doc_freq` | 1 |
| `pos` | noun |
| `lemma` | تَجْرِيدٌ |
| `lemma_din` | taǧrīdun |
| `root` | جرد |
| `voc_source` | unresolved:1 |
| `morph_confidence` | best_partial |
| `pos_agreement` | agree |
| `layers` | frontmatter:1 |
| `first_record` | frontmatter-00001 |
| `kwic` | «التجريد» الصريح لأحاديث الجامع الصحيح المؤلف |
| `search_key` | التجريد |
| `gloss_msa` | the + stripping |
| `lane_root` | جرد |
| `classical_keywords` | tropical, assumed, hair, having, himself, locusts, divested, land, body, free, stripped, though, places, herbage |
| `classical_sense_sample` | He was bright in respect of what was unclad of his body, or person. |
| `classical_senses_more` | A sect of the Zeydeeyeh, ( of the Shee'ah, TA,) so called in relation to Abu-lJárood Ziyád the son of Aboo-Ziyád: ‖ ] he strove or laboured, exerted himself or his power or efforts or endeavours or ability, employed hims … |
| `lane_entry_count` | 30.0 |
| `literal_sense` | *(null)* |
| `technical_sense` | *(null)* |
| `domain` | *(null)* |
| `divergence` | developed_sense |
| `overlap_score` | 1.0 |
| `match_id` | التجريد#6fc1d3 |
| `workbookMatchId` | التجريد#1 |

Homographs on key `التجريد`: التجريد#6fc1d3 (freq 1)
