# District landmark assets

The catalogue contains the original four elevation models, the flight project's unique Geunjeongjeon model, and 250 additional sites (10 per Seoul district). Existing elevation asset records and GLB files are retained; their hashes are recorded in `DISTRICT_LANDMARK_PROVENANCE.json`. The original four footprint-replacement lists are retained too.

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

Rebuild with:

```sh
.venv/bin/python scripts/match_district_landmarks.py
.venv/bin/python scripts/build_district_landmarks.py
node scripts/verify_district_landmarks.mjs
```

The generator refuses an incomplete or duplicated 250-site selection and overlapping assigned footprint IDs. It checks original model hashes and exact original asset-record text after writing the expanded manifest. `LANDMARK_ASSET_VALIDATION.json` records the independent Three.js GLTFLoader pass over all 255 files, including hashes, dimensions, floor origins, finite positions, unit normals, indices, triangle counts, and replacement-list presence. Browser scene screenshots are separate evidence; this asset validation alone does not certify application performance.

The linked OSM source records retain their ODbL attribution in the provenance JSON. Existing source data and SQLite databases are not changed.
