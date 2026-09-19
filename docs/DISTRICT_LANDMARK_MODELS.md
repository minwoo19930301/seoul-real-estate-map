# Current catalogue

A further 605 apartment sites bring the current catalogue to **1,160 models**. See [400-household priority expansion](APARTMENT_400_EXPANSION.md) for confirmed household counts, smaller/unknown-count sites and district shortfalls. The first two batches below remain preserved unchanged.

# District landmark assets

The first two expansions produced **555 models**: the original four elevation models, the flight project's unique Geunjeongjeon model, the first 250 sites (10 per district), and a further **300 apartment complexes (12 per district)**. All 255 previously published model files, full asset records, and footprint-replacement lists are preserved unchanged. Existing elevation asset records and GLB files are retained; their hashes are recorded in `DISTRICT_LANDMARK_PROVENANCE.json`. The original four footprint-replacement lists are retained too.

## Geometry and evidence

`build_district_landmarks.py` builds actual 3D meshes from retained building polygons in the read-only `data/buildings.sqlite`. A complex contains the selected individual building footprints, including their distinct orientations, concave outlines, setbacks between buildings, and source height/storey differences. It is not a grid of repeated placeholder boxes.

Source heights remain **source-reported, independently unverified**. Rooftop plant remains within the height envelope when a source height is available. Missing heights use source storeys × 3.05 m. The documented fallback is 15 storeys for apartments and 3 storeys for civic buildings. Window bays, mineral/glass colours, roof plant, and roof proportions are visual estimates, not architectural drawings or photogrammetry. Some source buildings lack both height and storey information; their silhouette height is correspondingly approximate.

Six sites receive additional identifying geometry: the open arch of Independence Gate, the National Assembly's green dome, the shallow KSPO roof dome, hipped roofs at Bongeunsa Jinyeomun and Hyeonchunggwan, and red structural accents at Parc1 Tower 1. Independence Gate's overall height/width follow [Seoul Archives](https://archives.seoul.go.kr/post/1678) (14.28 m / 11.48 m); the opening, cornices, and depth are estimated. The National Assembly dome uses the 64 m base diameter in the [National Archives description](https://theme.archives.go.kr/next/koreaOfRecord/parliamentBldg.do); the 20 m dome rise follows its historical design narrative, while the roof level is an estimate. These special silhouettes do not imply measured facade reconstruction. DDP Fashion Mall is the named building selected in the database, not Dongdaemun Design Plaza.

## Membership and placement

`match_district_landmarks.py` reserves exact civic building IDs first. Apartments use apartment-classified footprints around their source coordinate, with competing apartment records limiting membership. This is an **approximate complex-membership assignment**, not a cadastral boundary match. Only assigned footprints are hidden when their GLB is actually rendered. Completeness of an apartment complex's membership is not asserted. Each asset's assignment radius, maximum centroid distance, source building IDs, and confidence are in the provenance JSON.

An attempted Overpass boundary fetch returned HTTP errors; no downloaded residential-boundary geometry is included or treated as verified evidence. The query is retained only for reproducibility.

The meshes use metres, Y-up, X-east/Z-south, identity roots, and a shared floor at Y=0. Coordinates are adjusted to the actual model-bounds centre using Mercator metre conversions. New assets have `yawDegFromEast=0` because building orientation is already in their vertex coordinates. Each site's terrain datum is sampled at its anchor by the runtime; the model does not claim per-building surveyed terrain offsets.

## Performance and verification

Each new asset has at most three material batches. Geometry is indexed and vertex colours use packed normalized RGBA bytes. There are no textures or external resource dependencies. New models request display from zoom 14.5; runtime limits govern nearby loading and resident models.

To reproduce the first batch on the original 255-model baseline:

```sh
.venv/bin/python scripts/match_district_landmarks.py
.venv/bin/python scripts/build_district_landmarks.py
node scripts/verify_district_landmarks.mjs
```

The generator refuses incomplete or duplicated selections and overlapping assigned footprint IDs. It checks original model hashes and exact original asset-record text after writing the expanded manifest. `LANDMARK_ASSET_VALIDATION.json` records the independent Three.js GLTFLoader pass over all 555 files, including hashes, dimensions, floor origins, finite positions, unit normals, indices, triangle counts, and replacement-list presence. Browser scene screenshots are separate evidence; this asset validation alone does not certify application performance.

The linked OSM source records retain their ODbL attribution in the provenance JSON. Existing source data and SQLite databases are not changed.

## Additional 300 sites

The second selection was drafted by GPT-5.6 Luna at low reasoning effort and checked against retained apartment records, Seoul district polygons, OSM site identifiers, and existing source-footprint ownership. These are representative apartment complexes ranked by source household counts, **not a verified price-based ranking**. The earlier Astra-authored mesh generator was extended with an additive mode. No fresh Astra sub-agent ran for this batch because the session agent limit was reached.

Candidates remain at least 100 m from existing candidate/model anchors and other new candidates. Shared-address/unresolved coordinates are excluded. Eleven initial candidates with no available matching footprint were replaced from the reserve pool. All 300 final sites have nonempty source geometry, and no footprint is reassigned from an existing model. The same estimates and complex-membership limitations described above apply.

The final selection is in `landmark-candidates-expansion-matched.json`; its per-building evidence is in `LANDMARK_EXPANSION_PROVENANCE.json`. `landmark-expansion-unmatched.json` records rejected draft candidates, not missing final models. `tests/fixtures/preserved-255-landmarks.json` freezes previous geometry hashes, canonical full-record hashes, and exact replacement memberships.

Reproduce the expansion starting with the 255-model catalogue at commit `1ad7d15` and the retained read-only databases:

```sh
.venv/bin/python scripts/select_landmark_expansion.py --boundaries /path/to/seoul-flight-game/assets/full-seoul/source/districts.geojson
.venv/bin/python scripts/match_district_landmarks.py --additional-pool docs/landmark-candidates-expansion-pool.json
.venv/bin/python scripts/build_district_landmarks.py --append-candidates docs/landmark-candidates-expansion-matched.json --expected-count 300
node scripts/verify_district_landmarks.mjs
```

The pool is the draft followed by reserves, in that order. Append mode refuses existing asset IDs or filenames. The default original-batch mode refuses to overwrite an already expanded catalogue. Runtime limits remain four concurrent requests, 32 nearby rendered assets, and 48 resident assets; the full catalogue is not eagerly downloaded.

Browser automation uses a temporary Vite development server (`PLAYWRIGHT_BASE_URL=http://127.0.0.1:4174`), because its inspection API is intentionally absent from production. The production build at port 4173 is separately checked for the 555-entry catalogue and visible rendering.
