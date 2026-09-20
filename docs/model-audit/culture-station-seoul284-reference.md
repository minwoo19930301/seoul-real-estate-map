# Culture Station Seoul284 — individual Blender study

This asset reconstructs the **old Seoul Station only**, not the modern railway concourse. It is manually authored from the operator's exterior photographs and floor plan, anchored to the existing geographic source footprint. It is not measured architectural CAD, photogrammetry, or a claim that every current surface has been surveyed.

## Candidate audit and selection

| Existing landmark | Current evidence and geometry | Decision |
| --- | --- | --- |
| Amorepacific headquarters | Current authored asset has 19,040 triangles, a hollow central volume, three hanging-garden openings and individual fins. [Architect's project description](https://davidchipperfield.com/projects/amorepacific-headquarters) identifies these same defining features. | Preserve this authored model in this round. No comprehensive dimensional accuracy claim. |
| Dongdaemun Design Plaza | Current authored asset has 18,296 triangles and a continuous lofted body, secondary lobes and sunken plaza. [Architect's project page](https://www.zha.com/projects/architecture/dongdaemun-design-plaza?disclaimer=true) describes the flowing landscape and connected exhibition spaces. | Preserve this authored model in this round. It already has a distinctive non-box silhouette. |
| Old Seoul Station | Current `reference-flight-seoul-station` has 2,438 triangles. Its old-station front runs approximately 44m east–west and faces north, while the geographic old-station footprint is approximately 139m north–south and the official photos show an east-facing central entrance. It also includes an approximately13.5×30m game-scale modern-concourse fragment. | Rebuild the old station individually, retaining the red brick, stone, copper dome and clock supported by photographs. Do not reproduce or claim the compressed modern concourse. |

The first two are source/structural spot checks, not a new photograph-by-photograph recertification. Flight source revision: `e007f5bcce37575904beec7edb8cc4036add7635`; source module `seoul-station.mjs`. Its existing exported SHA256 is `5f3d38c32702e45cf83e2a6cffc30f3de87a379cedffbd3b4e31b0b025887c8f` and its complete game scene measures approximately77.2×35.82×77.2m, including scenery.

## Primary references actually inspected

- [Official history/introduction](https://seoul284.org/cms/content/view/253): exterior photographs, restoration chronology and construction materials. This page describes red brick, granite/artificial stone and the domed historic station. It distinguishes the new railway station opened in2004 from the restored old building.
- [Official full frontal exterior photograph](https://seoul284.org/jnrepo/upload/contentCrawler/202109/ad8fccb0bd43472eba04c668c92ed7e2_1631253712381.jpg): central great arch with clock pedestal, copper dome and lantern, small flanking turrets, red-brick main wings, pale horizontal belts, shaped end gables, low northern and southern annexes. Local review file `/tmp/seoul284-evidence/official-21.jpg`.
- [Official upper facade photograph](https://seoul284.org/jnrepo/upload/contentCrawler/202109/1163dfc827c44f4ab362c2dc04e2d3fc_1631253712097.png): dome fanlight, copper seams, lantern, stone arch moldings, small turrets and roof profile. Local review file `/tmp/seoul284-evidence/official-14.png`.
- [Official oblique exterior photograph](https://seoul284.org/jnrepo/upload/contentCrawler/202109/6857f0069e6645ad81b9ed49560ad8d5_1631253712206.jpg): projecting central entrance, wing relief, pale corner quoins and green-framed windows. Temporary foreground artwork is excluded. Local review file `/tmp/seoul284-evidence/official-16.jpg`.
- [Official space guide and inline floor plan](https://seoul284.org/space/menu/256): central hall, differentiated north and south rooms, north RTO and protruding entry. The central hall description records12granite columns and east/west semicircular windows. The plan confirms the building is not a short symmetrical rectangle. Local floor-plan review `/tmp/seoul284-evidence/floorplan.png`.

The photograph upload paths date to2021; capture dates are not stated. No external photos or floor-plan graphics are embedded in the GLB or Blender file. Source images remain separate review references.

## Geographic ownership and placement

Coordinates are derived from the retained source geometry, not the game registry center. Model origin is **126.97158°E,37.555877°N**, near the historic central hall. Blender axes are eastX, northY, upZ; glTF export is eastX, upY, southZ. Geometry is baked with no additional yaw. The long axis follows the north–south footprint and the main facade faces east.

| Source | Meaning | Ownership |
| --- | --- | --- |
| `d8469ff5-7c6b-4514-8e0d-da239407bbda`, [OSM w759569673](https://www.openstreetmap.org/way/759569673), local version5 | Old station, approximately139m north–south by28m east–west | New model owns this parent. |
| `36356163-6139-3732-A335-333337356337`, [OSM w1103628080](https://www.openstreetmap.org/way/1103628080), local version1 | Northern RTO part | New model owns this exact child. |
| `a78efc86-7dae-4e63-8e4b-d672a7eff741`, [OSM r7307085](https://www.openstreetmap.org/relation/7307085), local version23 | Modern Seoul Station, geographic bounds126.9694482–126.9721195E /37.5523724–37.5563259N | **Not owned or hidden by this asset.** Retain its source geometry and other independent models. |

The old Flight reference owns only the same two historic IDs. `supersedes: ["reference-flight-seoul-station"]` removes that complete game reference, including its inaccurate tiny modern fragment; it does not claim the modern station footprint. Existing GLB bytes are untouched. No plaza, railway tracks, bridge, roads, neighboring towers or ground plane are added.

## Individual construction

The source outline is retained as a shallow base, with distinct architecture groups:

1. Central projecting stone portico: actual open door bays, recessed great semicircular window, thick voussoir arch, fine radial joints, clock pedestal and geometric dial, open balustrade strips.
2. Broad copper dome: curved ellipsoid, metal seam ribs, east-facing thermal window, open-sided lantern and finial. Two smaller turrets flank it. A second official-front-photo review narrowed the entire dome/drum/fanlight/lantern ensemble to0.74of its initial study width, giving a dome-to-main-arch span ratio about0.65; upper dome height was reduced to0.82and the small turret shafts extended2.8m with taller arched slit windows. These remain photograph interpretations.
3. Unequal north/south wings: brick facades, granite lower floor, stone stringcourses, green window frames, ground arches, upper tall windows and corner quoins.
4. Projecting end pavilions: individually located against source plan steps, shaped Renaissance gables and attic windows, hip roofs and eyebrow dormers.
5. Low south VIP annex: its actual stepped footprint and projecting portal.
6. Long low north RTO: its separate source child, stepped frontage and lower roofline.
7. Conservative rear facade, without invented ornamental details.

The model intentionally makes the central arch, dome and building-length corrections substantive geometry changes. It is not the old block model recolored.

## Dimensions and uncertainties

- Source parent and child heights are null. **32.29m finial height is a photographic estimate**, not a published height. The main wing eaves around14.5m and low annexes around7m are likewise interpretation.
- Source reports parent3floors and RTO2floors. The official guide covers main1F/2F rooms; these records do not establish equal floor heights. The low RTO roof follows exterior appearance, not a generic floors×height rule.
- Window widths/counts, stone profiles, dome curvature, roof pitch and brick color are hand interpretations. Small sculptural detail is simplified. The rear is less documented and is deliberately restrained.
- The clock hands illustrate a clock face, not current time. Temporary art, advertisements and unverified present-day signage are not reproduced.
- The official plan and source outline establish orientation and differentiated wings; they do not supply measured elevation drawings.

## Reproduction and proof

Build through the real MCP driver on dedicated port9876:

```sh
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute --port 9876 --script scripts/bespoke/culture_station_seoul284.py --record data/model-source/bespoke/culture-station-seoul284/mcp-build.json
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute --port 9876 --script scripts/bespoke/culture_station_seoul284_render.py --record data/model-source/bespoke/culture-station-seoul284/mcp-render.json
python3 scripts/bespoke/culture_station_seoul284_validate.py
```

The ignored stage contains editable `.blend`, `.glb`, `bundle.json`, `report.json`, actual MCP call records, viewport capture, four review views and exported-byte validation. Inspect `View_East_Front.png` against the official front photograph and `View_Plan.png` against the source outline before publication. Shared runtime, manifests, legacy models and terminal artifacts are outside this authoring scope.
