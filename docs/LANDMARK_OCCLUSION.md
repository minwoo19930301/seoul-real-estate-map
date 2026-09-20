# Landmark replacement and overlap checks

The authored models were present, but ordinary source extrusions and procedural GLBs could still enclose them. Three causes were reproduced: unmatched same-building identities where the model covered less than 65% of a source polygon; upper-floor `building_part` features surviving after their parent was replaced; and compound procedural models that contained both a landmark and other buildings.

The renderer gives the original five Flight landmarks and reference models priority. Only a successfully drawn landmark suppresses overlapping procedural assets, using shared source identities rather than a geographic exclusion circle. Other buildings in a skipped compound retain their source representation (reported-height solids, or footprints when height is unknown). Source parts inherit exact parent identity. Delayed, failed, disabled, and culled references leave fallback representations available.

Reviewed identities and recursive parent relations are recorded in `REFERENCE_MODEL_INTEGRATION.json`. Separate neighbouring buildings are explicitly retained, including LS Yongsan Tower near Amorepacific and Park Habio beside Garden Five. No source database or preserved legacy asset is deleted.

Goldpark is placed at the reviewed third-complex location. Garden Five’s four Life halls are fitted to their individually named footprints; unverified auxiliary game scenery crossing neighbouring sites is excluded. The other 124 reference GLBs remain byte-identical.

## Browser evidence

`tests/landmark-overlap.spec.ts` uses independently observed source IDs for Jongno Tower, GFC, Myeongdong Cathedral, Samsung Town, SKY-L65, Hyperion, Trade Tower, Lotte World Tower, D-Cube, Dongnimmun and Cheongwadae. All 11 sites passed with no active procedural collisions or browser errors. It checks actual rendered source features, active procedural assets, restoration when models are disabled, preservation of neighbouring buildings, and pending/HTTP 404 fallback.

- `landmark-overlap-before.json` and `landmark-overlap-additional-before.json`: reproduced original collisions.
- `landmark-overlap-browser-check.json`: source parts and procedural duplicates after the fix.
- `landmark-overlap-neighbors-check.json`: retained neighbouring buildings.
- `landmark-overlap-fallback-check.json`: fallback while a reference is pending and after HTTP 404.

Before/after views: [GFC before](qa/overlap-before-gfc.png), [GFC after](qa/overlap-after-gfc.png), [Jongno Tower before](qa/overlap-before-jongno-tower.png), [Jongno Tower after](qa/overlap-after-jongno-tower.png).

Validation: 13,697 Node tests passed; TypeScript type checking passed; the 11-site browser regression, neighbour preservation, model-toggle restoration, pending/HTTP 404 fallback, and existing reference landmark regression passed.

These are illustrative architectural models, not surveyed building meshes. Ordinary neighbouring buildings may naturally obscure a landmark from some camera angles.
