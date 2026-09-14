# Independent QA review

Date: 2026-09-08. Scope: the local Seoul contour app, its SQLite API, and derived terrain display. No remote publication or account changes are part of this review.

## Status

- Independent SQLite/backend/frontend source review and an actual application browser smoke test are complete. Broader interaction scenarios were executed separately by the frontend owner; those results are distinguished below.
- Existing Playwright module: `/private/tmp/local-llm-desk-browser-audit/node_modules/playwright/index.mjs`.
- Installed Google Chrome launched in a separate headless profile: `152.0.7977.82`; a WebGL2 context was created successfully.
- The initial sandboxed browser launch failed with SIGABRT/EPERM. An approved escalated retry passed. The application was opened in a separate headless Chrome profile at `http://127.0.0.1:4173`, viewport 1280 × 844.

## Acceptance checks

### Source observations and user-facing meanings

- Original contours retain their recorded elevations and 5 m interval; point observations retain their own recorded coordinates and heights.
- A nearest-point result is labeled as the nearest surveyed/source point, with its location and distance from the click. It is never labeled as the clicked location's measured height.
- Source reference year, file publication date, contour interval, and independent vertical accuracy are distinguished. A 5 m contour interval is not an accuracy claim.
- Low contour density, missing source coverage, and low relief are not treated as interchangeable states.
- Derived terrain is consistently labeled estimated/interpolated. It is not a 1 m-accuracy claim or a reconstruction of bridges, retaining walls, or apartment podium levels.

### API and data contract

- Valid bbox queries return the correct geographic region, in coordinates expected by the frontend; transformation from source EPSG:5174 is verified against known sample locations.
- Reversed bounds, non-finite numbers, missing parameters, latitude/longitude outside valid ranges, and unreasonable query extents receive bounded, explicit responses.
- No-result queries are represented explicitly, including outside source coverage. Empty or invalid queries do not silently turn into whole-city responses.
- Point-query result coordinates, reported distance, and source feature ID agree with the source record. SQL parameters are bound, rather than string-interpolated.
- Geometry payloads have sensible feature/vertex limits; truncation, simplification, or omitted layers are visible in metadata rather than silently appearing as complete source data.

### Terrain and MapLibre

- Raster DEM encoding and source elevation units are consistent. Sample pixels decode back to expected terrain values within the encoding precision.
- Georeferencing, tile bounds, and terrain/contour alignment are checked at representative locations and map edges.
- NoData and interpolation-support boundaries do not create false pits, walls, or zero-height terrain at edges.
- Terrain exaggeration is a visual parameter. Numeric point/profile readouts do not use exaggerated display elevations as actual source heights.
- 2D/2.5D switching preserves map location, keeps source overlays aligned, and clearly indicates estimated terrain when enabled.
- Tests use ordinary viewport requests to the online OSM basemap only. Attribution remains visible; no prefetch, citywide tile crawl, or offline tile bundle is created.

### Browser scenarios

- Desktop and narrow mobile layouts: readable controls, non-overlapping legends/attribution, and no horizontal overflow.
- Navigate to the prepared Seongsu, Daechi, and Sangdo samples; source contours and points appear in the intended areas.
- Toggle each layer, click source features, request a nearest point, and verify semantic labels plus loading/empty/error states.
- Enable estimated terrain, change exaggeration if available, rotate/tilt, then return to 2D; numerical source observations remain unchanged.
- Observe browser page errors and failed local API/asset requests separately from any external basemap/network failures.
- Save only targeted screenshots needed to substantiate actual observations; screenshots do not certify geographic or vertical accuracy.

## Findings and evidence

### SQLite/source inspection

- Opened `data/terrain.sqlite` with SQLite `mode=ro`; `PRAGMA integrity_check` returned `ok`.
- Verified 8,570 contours and 45,870 source points. Contour values range from 5 to 770 m; point values range from -0.54 to 740.2 m. These are source values, not independently verified terrain extrema.
- Metadata distinguishes source year 2023 from file date 2025-03-20, records source EPSG:5174, and identifies the vertical datum as unverified.
- Source extent is explicitly a data bounding rectangle, not the Seoul administrative boundary: `[126.76581496652611, 37.428235819558054, 127.18412343703505, 37.70145487025788]`.

### Backend source review

- `TerrainAPI.elevation` returns `query` and `nearest.coordinate` separately, uses the native projected coordinates to calculate distance, and returns no match at distances >= 1,000 m or outside the source bounding rectangle. Frontend source uses a separate source-point marker and distance; the nearest source height is explicitly not labeled as the clicked location's height.
- `TerrainAPI.features` clips to the requested view/source extent, selects precomputed display simplifications by zoom, and supplies `truncated`, `spots_sampled`, `simplified_m`, and the actual contour interval in response metadata. The frontend must surface omitted/sampled display data rather than imply every source feature is shown.
- SQL values are bound parameters. Terrain connections use `mode=ro`; writable bookmarks are stored in a separate SQLite file.
- Non-finite/reversed/out-of-range coordinates, unsupported contour intervals, duplicate query parameters, and malformed bookmark payloads have explicit validation paths. This reviewer did not independently execute the backend owner's HTTP regression suite.

### Independent application browser evidence

- The corrected MapLibre worker URL and `style.load` initialization were verified in a freshly opened browser context: `mapLoaded: true`, `terrainReady: true`, `is25d: false`.
- Initial Sangdo viewport loaded 282 contours and 560 source points. Response metadata reported 5 m contour interval, 2 m geometry simplification, `spots_sampled: true`, and `truncated: false`.
- The visible sidebar stated that some source points are displayed to avoid overlap. This verifies the corrected `spots_sampled` API/frontend contract in the running app.
- During this smoke test: **0 page errors, 0 failed requests, and 0 local HTTP responses with status >= 400**. This observation covers initialization and the initial view, not an unlimited runtime or every map tile.
- Visible map attribution included Seoul/NGII source attribution, the derived-terrain description, and OpenStreetMap contributors. No bulk basemap requests or offline bundles were made by this review.
- The independent test did not execute the subsequent mobile, bookmark, or 2.5D control scenarios. The frontend owner separately reported five passing Playwright scenarios covering initial data/bookmark persistence, 2.5D/exaggeration with unchanged numeric source readings, place/interval/whole-city navigation, blocked external resources, and mobile interaction. These are owner-reported results, not duplicated independent evidence.

### Integration findings and remaining limits

- The initial frontend type mismatches (`points_sampled` versus API `spots_sampled`, and number versus string feature/bookmark IDs) were reported and corrected by the frontend owner. The point-sampling notice was independently verified in the browser.
- A separate validity PNG does not automatically mask a MapLibre `raster-dem` source. The owners added explicit coverage raster tiles and a visible legend for unsupported/interpolation-padding regions. At the source snapshot reviewed, coverage visibility was tied to 2.5D mode while hillshade was enabled by default in 2D; this remaining display-consistency issue was reported to the frontend owner for correction.
- Numeric point inspection reads `/api/elevation` source observations; it does not read exaggerated MapLibre terrain elevations. This is confirmed by source review, with actual control interaction covered separately by the frontend owner's tests.
- Independent survey/vertical-datum validation, bridge/deck or retaining-wall reconstruction, quantitative pixel/contour alignment checks, and full-city visual inspection were not performed. A successfully rendered terrain surface is not evidence of vertical accuracy.

The acceptance list above is a review checklist, not a claim that every item has been independently tested. The observed results and remaining limits are recorded explicitly in this section.
