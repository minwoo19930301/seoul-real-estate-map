# Residential facade module

`scripts/residential_facade.py` exports:

```python
residential_geometry(mesh, poly, height, floors, kind, seed) -> bool
```

Supported kinds are `villa`, `apartment`, `mixed-use`, and `officetel`. Unknown kinds and invalid polygon/height inputs return `False` before writing vertices. `mesh` follows the existing `build_district_landmarks.Mesh` contract (`solid`, `quad`; material indices 0–2). The module does not import the builder, read source databases, write GLBs, modify the manifest, or control runtime layers.

## Source boundaries and modeled detail

The caller supplies one valid source Polygon in local metres, the positive height envelope, floor estimate, kind and deterministic seed. The full polygon orientation, exterior, concave boundary and holes remain intact; there is no replacement by a bounding rectangle, no plan enlargement, and no inserted tower. `Mesh.solid` retains the polygon and cuts holes from the roof. The module does not classify buildings from names or infer household counts.

The caller decides what to do when measured height or storeys are missing. This module never computes a height from floor count or building type. An absent/zero floor count gives one displayed storey, without changing the supplied height; supplied floor counts are capped at 200 for bounded sampling. All positions remain between y=0 and the supplied height, including the roof-edge course. There is no below-ground foundation, rooftop addition, scale multiplier or claimed terrain correction.

Materials and detail layout are **procedural visual estimates**, not surveyed, photographed or building-specific architectural reconstruction. They do not establish that a particular source building has a real balcony, commercial ground floor, staircase at that location, or a particular number of windows. No photographs, signage, logos, private interior layouts, or downloaded architectural images are used.

| Kind | Modeled appearance | Explicit limitation |
| --- | --- | --- |
| `villa` | Warm stone/brick-colored walls, brick plinth, window dividers, a few shallow slab/railing reliefs | The relief evokes balconies; it is not a full projecting room or a claim that balconies exist on that facade. |
| `apartment` | Repeated dwelling windows, window sills, an applied vertical stair/service-core color strip | Core placement is an illustrative facade division, not an added tower or a measured circulation plan. |
| `mixed-use` | Dark ground-floor commercial-style facade, broad storefront glazing, a separation band, dwelling windows above | The podium is facade treatment within the exact original extrusion; no larger retail footprint or setback is invented. |
| `officetel` | Narrower/taller glazing, cooler wall colors and selected thin floor bands | No assertion of unit count, use mix or building-specific curtain-wall design. |

Glass/detail surfaces are offset 4–14 mm to avoid coplanar flicker. Villa balcony relief reaches at most **40 mm** beyond a source edge. These minute display offsets are the only plan protrusions. Interior courtyard edges receive windows/bands but no balcony relief. Materials use the existing opaque mineral (0), window glazing (1) and roof/cap (2) batches; no additional draw-call groups or textures are introduced.

## Bounded geometry cost

Only the 12 longest eligible perimeter edges receive facade detail. Shorter/skipped source edges and every courtyard edge still belong to the exact base extrusion. Window density is capped at 4 bays per edge (3 for villas) and 24 sampled storey rows. Complex outlines receive fewer evenly distributed rows/bays within a per-face quota. Floor bands on mixed-use and officetel buildings are sampled at up to 6 elevations; they do not claim a complete depiction of all floor divisions.

The global detail allowance is `min(460, 11 + 26 * floors)` quads, divided among the selected source edges. The preserved source body/roof triangles are additional; a complex polygon's original vertex count is not silently simplified to meet an artificial total.

For a simple 16 × 12 m rectangle, the measured triangle counts were:

| Kind | 4 storeys | 20 storeys |
| --- | ---: | ---: |
| Villa | 230 | 930 |
| Apartment | 234 | 930 |
| Mixed-use | 186 | 650 |
| Officetel | 186 | 714 |

The rectangle's maximum permitted total is 240 triangles at 4 storeys and 930 at 20 storeys, independent of available detail opportunities. All material primitives remain in the same three batches. A local 100-building, four-storey villa generation check completed in approximately 0.215 seconds on this environment; this excludes source querying, serialization and disk writes and is not a full-batch throughput guarantee.

## Validation performed

On 2026-09-20 the module was exercised on all four kinds, at 1/4/20 floors, using an axis-aligned rectangle, a 37-degree rotated rectangle, an L-shaped concave polygon, and a polygon with a courtyard: 48 combinations. Four additional cases used actual retained source footprints from `data/buildings.sqlite`:

| Source building ID | Retained name | Test kind | Supplied height/floors | Triangles |
| --- | --- | --- | --- | ---: |
| `96765d63-39bd-4838-8b0e-861bbdd7a365` | 청암빌라트 | villa | 12.2 m / 4, explicit QA fallback because source height/floors are absent | 230 |
| `ac0d0074-e36a-437c-a3d5-28170192bccd` | 역삼르비앙아파트 | apartment | 12.2 m / 4, explicit QA fallback because source height/floors are absent | 240 |
| `bd1cf067-1d81-4548-a4bf-42ec74fce757` | 역삼우정에쉐르1주상복합 | mixed-use | Source 46 m / 15 | 570 |
| `458652e1-a8fa-4b43-92b3-4ad8a03bf7c9` | 르메이에르오피스텔 | officetel | Source 47 m / 15 | 622 |

These fixture names are QA examples, not selection instructions; household eligibility, authoritative type classification and preservation of already-modeled buildings belong to the caller's selection process.

All 52 cases passed finite position/normal checks, unit normal checks, y-min=0 and y-max within the supplied height. Synthetic cases additionally verified every plan vertex is covered by the source polygon buffered by 41 mm, including concavities and holes. Rectangle complexity limits passed. Unknown-kind and zero/negative/nonfinite-height calls returned `False` with an unchanged mesh.

A depth-buffered software preview of the four actual source examples was rendered and visually inspected at `/tmp/residential-actual-preview.png`. This is geometry QA, not an application-browser or deployed-service test. No global models, runtime code, manifest, deployment or source database was modified by this module task.
