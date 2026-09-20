# Reference-authored Seoul landmarks

This update adds the current Seoul Flight landmark geometry and a separately authored Maple Xi complex. The old catalog is retained as a fallback; the 113,123 older inventory entries are **not** claimed to have received photo-based reconstruction.

## Sources and scope

- Seoul Flight source revision: `e007f5bcce37575904beec7edb8cc4036add7635`, 94 individual Three.js landmark modules. The original five GLB landmarks already matched and remain unchanged.
- Author comments describe game-scale horizontal compression. Thirty-eight models receive documented scale/spacing adaptations; 56 retain the authored proportions because there is no defensible conversion factor. These are illustrative models, not architectural surveys.
- Tower Palace's seven residential components use individually identified retained OSM/Overture building centers. Shared game scenery is omitted where it would cover real streets or neighboring properties.
- Maple Xi: 29 residential towers, the 210–211 skybridge attached to tower 210, the Maple Road pedestrian bridge, and an explicitly labeled kindergarten planning model. Shapes are traced individually from GS Xi's numbered plan and georeferenced using three identifiable road intersections. Facades reference the developer's completed-building photographs published on 2025-11-26.
- Maple Xi's apartment name already existed in the apartment registry. Its independently modeled geometry was missing, while obsolete Hanxin complex pins obscured the current name. The reference entry supplies the model and canonical current pin without rewriting the underlying historical database.

Maple Xi's 2024 illustrative plan predates completion. Individual floor counts other than the documented 29-floor bridge towers, unseen elevations, facade dimensions, and ancillary dimensions remain estimates. The planned kindergarten is not proof of an independently surveyed completed building. Public-road alignment comes from a plan-to-map fit, not cadastral surveying. Original reference photographs are not redistributed.

## Runtime and retained data

`public/models/reference-manifest.json` adds explicitly identified replacements and current search places. Actual model triangles are projected onto source polygons to find covered footprints. Named identity exceptions are separately recorded, rather than masquerading as measured geometric overlap. No circular landmark exclusion zones are used. Existing multi-building assets are suppressed only when all their source footprints are accounted for.

References take precedence within the existing 32-visible / 48-resident GLB limits. Old source solids remain until a replacement draws successfully; failed reference loads can reload the retained generic model. Each Maple Xi building samples the terrain separately. The bridge is part of tower 210, preserving its height above ground. Legacy manifest, catalog shards, and original GLBs are immutable.

## Reproducibility and evidence

- `scripts/export_flight_landmarks.mjs`: export a pinned Flight revision; source hashes and cleaned geometry are recorded.
- `scripts/audit_flight_placement.py` and `scripts/adapt_flight_landmarks.mjs`: document author ratios, separate building width from component spacing, and preserve source materials.
- `scripts/build_maple_xi.py`: numbered per-building plan traces, source observations, facade construction, and georeferencing controls.
- `scripts/reference_placements.json`: reviewed placement overrides and named identity matches.
- `scripts/publish_reference_models.py`: publish the staged models and explicit source ownership.
- `FLIGHT_ADAPTED_EXPORT.json`, `MAPLE_XI_MODEL_RECIPE.json`, and `REFERENCE_MODEL_INTEGRATION.json`: source, model, and integration evidence.
- `reference-browser-check.json`: real map loading, placement, failure-free drawing, and current Maple Xi search verification.

Generation requires the local source databases and ignored staging directories. Hosted deployment uses the committed GLBs and manifests and does not regenerate models or require the author's private source checkout.
