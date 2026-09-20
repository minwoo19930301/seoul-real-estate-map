# Maple Xi 204 — individual primary-photo reconstruction

## Identity and ownership

- Exact retained original asset: `maple-xi-204`; candidate ID `bespoke-maple-xi-204`. Anchor `127.01468735690746,37.510894264704795`, original six-edge numbered-plan trace retained. Only that original ID is superseded. No cadastral footprint ID is invented.
- The official numbered plan puts204 on the highway row, immediately north of203, south of207, east of205. The March/February official aerials and GS completed panorama were opened in full and cropped only after following this row. The two separate plants, two long PV banks, middle L-roof notch and completed Xi sign agree between those views. The number is established by official-plan/site topology plus these features; a readable204 numeral is NOT present in these photo crops.
- Ground photographs W30–40 have captions mentioning204 but multiple tower objects and no readable number. Their details are excluded; neither proximity to an anchor nor caption alone establishes their identity. Club Xian/sunken plaza, shared garden and neighboring203/205/207 are excluded.

**Scale caution:** P has no usable scale bar or identified road width. Enlarged notes show25m is neighboring kindergarten height and47m is neighboring sports-facility height, not road dimensions. Independent metric width verification is unavailable.

## Primary source ledger

P: https://www.xi.co.kr/Files/cmsPage/20240205_132346_189001.jpg — official numbered plan, 2024 sales illustration; source SHA `1149145e0a0def2262558f488d1bb3373a2a0160486db4f1a07bf7d2de7aaaeb`.

A: https://www.xi.co.kr/Files/aptProcRateImg/20250403_170535_099001.JPG — March2025 official construction aerial; SHA `2facade0dd5c6d5c58507856b90a911e4a692d7804e088ce900650ae6bd64655`. `references/march-204-candidate.jpg` crop original `(620,1190,1540,3050)`; `march-roof-detail.png` nested crop, no generative restoration.

B: https://www.xi.co.kr/Files/aptProcRateImg/20250403_170447_204001.JPG — February2025 official construction aerial; SHA `83c19e70c9a6bf5fb60816629ffe5f7c52b6615466ca88892cb703258aae2d4c`. `references/feb-204-candidate.jpg` crop `(3720,1200,4590,2300)`. Foreground203 is partly visible at bottom ofcrop, excluded from model.

C: https://beyondapartment.kr/media/pages/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja/56592f7013-1773801981/pokeoseu26.webp — GS completed panorama; SHA `6c0947b8d483709a5bc4e999ffb22e3a075ff3172e2c6a1f9507a1394cb1fabe`. Article https://beyondapartment.kr/focus/dosim-sok-jayeongwa-sarameul-itneun-jaieui-cheolhak-meipeulja . Original crop `(422,318,636,736)` enlarged3× only; night lights are not used as daytime facade pigment. `completed-white-face.png` and `completed-dark-face.png` are inspection crops only.

R: https://data.seoul.go.kr/dataList/OA-22424/S/1/datasetView.do — official building register, exact parcel167,204동, raw row575718, ID1000000000000007634105, **27floors,86.85m,129households**. Row SHA `ff0d22457a24a0fa2f6e69e9f4e2dac3088f1d7567bd8cdb4ec640227e9072d7`; complete raw_json retained in register-row.json and authored-input.json. Whole CSV SHA `ba00150bbc9b2343fd2ba2fbaaa0c723df7d5dabbbd820345a405e9aaa5162aa`.

Copyright photographs remain ignored local reference files and are not embedded in GLB/blend or proposed tracked artifacts.

## Orientation, individual differences and uncertainty

Geographic edge numbering follows exact source six-vertex clockwise ring; `orientation-audit.json` records each EN endpoint, outward normal and block camera. e4 is SE normal `(0.82790,-0.56088)`,39.03m; e5 SW `(-0.49992,-0.86607)`,40.73m. Color-coded Blender block renders reproduce the broad darkSE view from the highway versus broad whiteSW/narrow darkSE view from the south. Apparent photo widths are not treated as measured building widths.

- **e5 SW**: unequal broad living openings, paired windows, tiny square services and narrow openings. Two central gray continuous fields and a shallow recessedslot have their own geometry, not207's four-bank layout. Exact depth and per-window sash dimensions estimated. Top second bay is broader than its lower paired form as visible B/C. Four lower residential window rows above the groundportal have the continuous blue-gray sleeve visible in C: four rows were counted below the pale frame termination (approximately levels2–5). Its estimated metric span is4.3–16.3m. Ordinary SW glass is0.24m behind facade; pale horizontal beams0.18m thick, to avoid exaggerated slab shadows. The central recessed slot remains deeper.
- **e4 SE**: paleNEend with two unequal small window columns; dark region has unequal solid strips, opaque gray spandrels, recessed glass and proud sills/jambs. Its outer plane is not a single glazed sheet. Exact bank widths and sash subdivision are photographic estimates; no unsupported ground-photo balcony pattern is borrowed.
- **Roof**: two unequal rectangular plants on separate arms, small lower stair return, two PV arrays, open pale fins and rounded outside corners. The SW central crown interruption and SE Xi sign are photo-specific. Solar tilt, finpitch,plantsetbacks are estimated. No yellow night emissive color is baked into day materials.
- **Base**: low stone header, recessed glazing and pale portal visible in C; internal layout and exact entrances unverified. No four-corner generic pilotis scheme and no commongarden geometry.
- **e0/e1/e2/e3**: not confidently mapped to detailed photographs, so restrained provisional windows only. This is NOT all-face verified completion. Groundphoto identity is still missing.
- **Footprint metric limit**: the retained georeferenced illustrative outline encloses990.82m² while the legal register reports687.3329m² building area. Exterior/balcony versus legal boundary conventions have not been reconciled; retained plan dimensions are estimates, not a measured survey. Anchor/trace are preserved without unsupported rescaling.
- **Height**: 27 registered levels represented as a4.3m ground interval plus26×3.0m residential intervals; bodyroof82.3m, fincrown84.95m, tallestplant86.8m. These subdivisions are estimates within the86.85m registered envelope, not verified story heights; legal height's roofdatum remains unknown. The original29-floor94.56m generic geometry is not reused.

## Evidence and review

Real Blender4.5.11 GUI, isolated owned MCPport9878. Build/render/validation logs, editable blend and source-only procedural recipe accompany the candidate. Shared primitive math is permissible; no207 mesh, facade layout, roof plan or GLB is loaded. Glass-visibility rays supplement manifold/finite/ground0/height checks; numerical checks do not prove photographic accuracy. Root independently compared all seven final renders against the official aerials and completed photograph, accepted the photographed SW/SE and roof scope, and verified the frozen inputs before publication. Unseen faces and footprint scale remain unresolved as described above; this is not all-face surveyed completion.
