# Raemian One Bailey — first five waterfront buildings

This bundle reconstructs **101, 102, 121, 122 and 123 only**. It is **5 of the complex's 23 residential buildings**, not a complete model of the 2,990-household site. The remaining 18 residential buildings, ancillary structures, landscaping and entire-site podium are outside this bundle.

## Identity and primary evidence

- Official management code **A10023043**; Seoul apartment source OA-15818 row 2788 and K-apt weekly row 2721 agree on **2,990 households / 23 residential buildings** and Banpo-daero 333.
- Exact public building-register match: `district='서초구' AND road_key='서초구|반포대로|333|0|지상'`, parcel `서초구|반포동|land|1|0`. The 23 individually numbered residential rows sum to 2,990 households. The preserved `source-register.json` has original row numbers, register identifiers and source hashes. `numbered-source-mapping.json` contains all 23 identity correspondences; it is not a claim that all 23 were modeled.
- Official numbered site plan: <https://www.raemian.co.kr/sales/sub/s/onebailey?menuSeq=9573>. North is toward the upper left of the original plan. Georeferenced existing source outlines and their unique floor/height pairs resolve the numbered identities. The source geometry is from the local city building database, not survey CAD.
- Official completed tour, published **2023-09-26**: <https://raemian.co.kr/community/times/raemianHomeStyling/view.do?pg=1&searchStr=&searchType=&seq=98>. It assigns skycommunity facilities to **101, floor 9**, and **123, floor 11**. This does not mean 123 is one of the two tall riverfront towers.
- Architect RATIO completed photographs: <https://ratiodesign.com/project/raemian-one-bailey/>. `ratio-4.jpg` is the clear riverfront comparison; `ratio-1.jpg` shows a lounge's inner glazed face and large diagonal structural braces. `ratio-ledger.json` preserves exact original image URLs and SHA-256. The `/2026/04/` image path is a server upload path, **not an established photography date**.
- General-sale floor chart `menuSeq=9575` covers selected sale buildings; it does **not** give individual floor charts for these five buildings. It was not used to assert their wing-floor counts.

## Verified mapping and height interpretation

| Building | Source footprint | Register floors | Register height | Households |
|---|---|---:|---:|---:|
| 101 | 4348b83d-8074-41db-b6fd-2a0220302d25 | 34 | 109.70 m | 139 |
| 102 | 18482853-b439-4fbc-a964-bbeb2c81c7cc | 14 | 44.70 m | 50 |
| 121 | 37167a22-89d6-41be-9768-691ce24bfc6b | 34 | 109.35 m | 130 |
| 122 | 1035924e-30e1-4e29-b8d8-894e48fd550e | 18 | 56.90 m | 56 |
| 123 | 9bf33339-8503-4c4d-a4a2-e34b800eb8a7 | 18 | 56.90 m | 68 |

**101 and 121 are the two tall riverfront towers. 123 is a lower L-shaped building.** The first bridge connects **101–102**, and the second **123–122**. 101 and 123 own the two bridge meshes respectively; each asset claims only its own residential source footprint.

The legal height datum does not establish the surveyed elevation of every decorative roof rail. The registered maximum is used as a conservative envelope. Individual lower-wing heights, intermediate tower-gallery floor/elevation, roof-setback widths, rear facade arrangement and individual vertical-member dimensions are interpretations of visible completed photographs. They are not measured architectural drawings.

The separate skycommunity register row gives **6.1 m** height; it does not establish the above-ground bridge elevation. Model bridge bases are 27.9 m and 34.0 m, inferred from the stated ninth/eleventh floors using a 3.5 m base floor and approximately 3.05 m storeys. An exact bridge sill survey is unavailable.

## Visible components and limits

- Tall 101 and 121: grey vertical piers and paired residential window bays, a physically recessed middle gallery with side supports and setback glazing, a forward main spine and lower unequal side-wing terraces, thin open roof railings and mesh roof-name lettering. Each has its own source dimensions/height. 101 additionally has a low return wing; 121 does not.
- Low 102, 122 and 123: individually partitioned L outlines, unequal wing heights, navy opaque panels, contrasting white vertical dwelling bays, narrow casement windows and glazed lounge-support corners. The actual source outlines retain their small offsets; profiles are not identical rectangles.
- Two enclosed lounges: different spans and elevations, deep champagne/light metal envelope, outer reflective glazing, finer mullions, internal broad diagonal braces. Interior furnishings are not reconstructed. The RATIO inner-lounge image alone does not independently establish its identity. Numbered official completed photographs now verify both bridge pairs and their separate low open connectors. `tour-kinetic_field__0452.jpg` shows 101 and 102 labels; `tour-_C6A3965.jpg` shows 123 and the Luminary Hill bridge. Connector deck elevation6.6m and dimensions remain photo-proportion estimates. Central rooflight/pergola intricacies are simplified; the exterior envelope and internal diagonal members are explicitly modeled.
- No invented site-wide foundation, plaza or extra neighbor ownership. Low roof equipment not visible in the selected photos is omitted. Inaccessible rear elevations and internal courtyards are conservative continuations, not confirmed construction drawings.
- The reference photographs remain ignored local comparison files only; they are not embedded in the blend/GLBs or redistributed as textures.

## Restoration and independent reproduction

The editable `raemian-onebailey-family.blend` is directly openable in Blender 4.5.11 LTS. Each numbered collection contains authored geometry; the review collection contains only ground, lights and cameras. GLBs are exported separately in local east/north/up metres at the per-building geographic anchors, with the standard glTF east/up/south conversion. No texture images or camera/light objects are exported.

`build.py` reads the adjacent self-contained `recipe.json` and creates the model via actual Blender MCP. No network access or city database is required to rebuild from that recipe. `prepare.py` is the optional identity/partition preparation step; it requires Python + Shapely and the adjacent `numbered-source-mapping.json`. `map_sources.py` and source extraction are audit work, not required model build steps.

```
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute --port 9876 --script modeling/bespoke/raemian-onebailey-family/build.py --record data/onebailey-rebuild-mcp.json
python3 modeling/bespoke/raemian-onebailey-family/validate.py
```

Each new model supersedes only `fallback-onebailey-<its own number>`. Root separately partitions the previous 19-building generic compound. The other 14 members of that compound and other neighboring models remain independently renderable.

## Final photo-led refinements

The enlarged RATIO river photograph shows small service windows beside three narrow dwelling-window stacks and a wider living-room stack on the raised front spine. The lower portion has a long recessed vertical slot and broader glazed bays. These are modeled as different facade regions; the old uniform six-column front grid and concentric stepped crown were removed. Two smaller outer gallery openings flank a wider middle opening. The ONEBAILEY and RAEMIAN signs are editable mesh lettering on their respective towers.

The later-numbered operator photographs confirm pale courtyard-facing service walls on the low wings, contrasting with navy return faces and glazed bridge supports. Those newly visible faces were revised rather than retained as the earlier generic navy continuation. Window trim was reduced so individual units do not read as thick floating plates.

The apparent black gallery-corner surfaces in an intermediate render were duplicate coplanar cap faces, not evidenced holes. The supporting solids now terminate below the continuous roof slab. No unsupported openings are retained there.

V3 exported maximum heights, including roof lettering, are101109.700m,10244.650m,121109.350m,12256.850m and12356.850m. Letter placement within the registered envelope is a conservative modeling choice, not a verified legal roof datum. The review above supersedes the earlier v1/v2 gallery attempts.

## Root final comparison

Root independently opened all seven final v3 renders and compared the 101/102 courtyard view with official kinetic_field__0452.jpg, 123/122 oblique with official _C6A3965.jpg, and the river silhouette with RATIO ratio-4.jpg. Reference photos stay private ignored comparison material, not textures.

V3 corrects the actual inner wing face, not the outer wing bounding box. The first lounge now has a continuous pale header, unequal broad attached glazed side supports, a recessed central glazed/pergola opening and dark bases. The second pair has its own larger opening/elevation; low separate connecting passages remain present.

101/121 retain forward grey residential spines, unequal lower wings, intermediate recessed galleries and roof lettering. Lower 102/122/123 preserve their own L outlines and white/navy wall areas. Inference is explicitly acknowledged for102/121/122/123; only representative101 is individually photo reviewed for family appearance.

Footprints, individual anchors, legal floors/heights and sole bridge owners101/123 were independently checked.122uses1035924e-30e1-4e29-b8d8-894e48fd550e. No terrain-covering site platform or neighboring buildings are claimed.

Final roof lettering is visible in river/east views and remains within the chosen legal-height envelope. This is an inferred placement, not proof that register height includes every letter. sourceHeightM retains legal height; heightM is the actual exported maximum.

Existing generic19-source compound remains partitioned without loss. Only five dedicated fallbacks are superseded;14remaining generic members stay visible. Four further numbered source polygons113–116 exist in the full23mapping but were absent from that original generic compound. Neither absence nor future work counts as completion.
