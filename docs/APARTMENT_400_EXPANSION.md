# Apartment expansion with 400-household priority

This batch adds **605 sites** to the previously published 555 models: **1,160 total**. It preserves every previous GLB byte, full manifest asset record, and footprint replacement list.

The target was 25 additional apartment sites per Seoul district, prioritizing 400 households or more. The retained source inventory and conservative footprint matching support 25 additions in 22 districts. Gangbuk has 19, Geumcheon 24, and Jongno 12. The remaining shortfalls are 6, 1, and 13 respectively. These are limits of this verified selection, not a claim that no other apartments exist in those districts.

- **445** additions have source-reported household counts of at least 400.
- **127** have smaller source-reported household counts.
- **33** are named apartment sites with source-classified residential footprints and **unknown household counts**. They are not counted as 400-household complexes. Some are individual apartment buildings, not large multi-building estates.

`apartment-400-selection-audit.json` contains per-district counts and selection exclusions. `apartment-400-matched.json` is the final inventory, `apartment-400-supplements.json` identifies the named-site supplements, and `APARTMENT_400_PROVENANCE.json` records each source footprint and its height basis. Household counts are retained source reports; no current census or price-ranking verification is claimed.

Candidates are ordered by household count, exclude existing asset/OSM-site identities and unresolved/shared-address coordinates, and retain the conservative 100 m anchor spacing. Matching reserves all previous footprint IDs before assigning any new site. Named supplements group named building components into one site and never reassign an existing footprint. This is approximate source-based complex membership, not a cadastral boundary survey.

The previous source-footprint modeling approach remains in use. Known source height envelopes are retained; missing heights, facade windows and rooftop details are estimates. Buildings in each model share one local floor plane, with terrain sampled at the model anchor. Source SQLite and Turso databases are not modified.

The catalogue validation ceiling is now 2,000. Rendering remains limited to 32 nearby models, four simultaneous model downloads, and 48 resident models. Increasing catalogue size does not increase these budgets. A 1,200-entry synthetic test exercises navigation and eviction; browser checks inspect the full 1,160-entry catalogue and selected old/new sites.

## Reproduction

Start from the 555-model baseline at `f5ce6c2`, with the retained read-only source databases and the scripts from this revision:

```sh
.venv/bin/python scripts/select_apartments_400.py --boundaries /path/to/districts.geojson --minimum-households 1
.venv/bin/python scripts/match_district_landmarks.py --additional-pool docs/apartment-400-pool.json --per-district 25 --allow-shortfall --output docs/apartment-400-matched.json --rejections-output docs/apartment-400-unmatched.json
.venv/bin/python scripts/supplement_named_apartments.py --boundaries /path/to/districts.geojson
.venv/bin/python scripts/build_district_landmarks.py --append-candidates docs/apartment-400-matched.json --expected-count 605 --provenance docs/APARTMENT_400_PROVENANCE.json
node scripts/verify_district_landmarks.mjs
```

The minimum of 1 enables smaller-site fallback after the largest complexes; unknown-count named sites are added separately. The generator refuses an existing asset filename or a provided provenance output that already exists. Historical evidence files remain available. The matcher’s optional shortfall mode does not manufacture missing candidates.
