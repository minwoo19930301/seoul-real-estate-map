# Historical apartment PR integration

Integrates PR16 and the stacked PR17–31 chain, preserving both commit ancestry and archived models. The historical catalog is coarse photo-informed modeling with completionCredit=false, not the current shared representative workflow or certified individual reconstruction.

## Ownership correction

Previously one overlap threw and disabled the entire historical layer. The loader now validates provenance and representative uniqueness, then excludes a whole compound if any source footprint belongs to a bespoke or reference model. It never strips ownership while leaving the same building geometry visible.

Three compounds are excluded: representative-a10026004 (7 overlapping footprints), representative-a10026207 (7), representative-a13822001 (28 of35). The remaining74 assets/719 footprints are retained. The seven non-overlapping Lake Palace sources remain on their original baseline instead of drawing a partially conflicting compound. No catalog asset or original GLB was deleted.

## Validation

Node13,914 tests passed; production TypeScript/Vite build passed. All13 publisher Python tests passed, along with the workflow Python suites. Browser checks passed for six shared-model/fallback paths (Family Town and Lake Palace) plus one historical/bespoke coexistence test. Both retained historical models and protected bespoke models draw; excluded compounds are absent from the active layer. Existing large-chunk build warning remains.

Adds Family Town9placements (one representative plus8shared copies), with unknown heights explicitly estimated and photo-inference limits retained. No new complete-complex claim.
