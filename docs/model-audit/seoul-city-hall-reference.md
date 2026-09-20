# Seoul City Hall: photograph and drawing led reconstruction

Status: Final Blender MCP exports accepted after independent source-photo/render comparison; local map integration verified. This is an individually authored architectural interpretation, not surveyed CAD or photogrammetry. No photographic texture or source photograph is embedded in either exported model.

## Evidence actually inspected

- [IARC Architects' project submission, ArchDaily](https://www.archdaily.com/457570/seoul-new-city-hall-iarc-architects): architect-provided description, ground-floor drawings and section; completion photographs credited to Archframe. The section establishes a recessed lower glass skin, a forward-curving upper eave, an occupied cultural volume suspended within the upper atrium, and office floors at the rear. The end photographs show **both** projecting oval lenses, the adjacent large triangular metal/glass patterns, fine rectangular glazing seams, and the deeper structural triangular lattice. These photographs—not an unbuilt competition proposal—guide the model.
- [Seoul's current main-building floor guide](https://www.seoul.go.kr/seoul/newoffice.do): 13 above-ground floors and a diagram of the separate new and historic buildings. The diagram is an explanatory illustration, not a metric as-built drawing.
- [Seoul's construction project record](https://news.seoul.go.kr/citybuild/archives/200904): new building B5–13F, former building retained and converted to the library, and the traditional eave design intention. SAMOO/Heerim are listed in the project delivery context; no unsupported claim that a generic SAMOO homepage supplied these details is made.
- [Seoul Culture Portal's library page](https://culture.seoul.go.kr/night/sub/nightFac/view.do?facId=9): official exterior photograph inspected for the long historic stone window rhythm, rusticated base, central portal and clock tablet, smaller rooftop lantern, patinated cap and flat parapets.
- [Seoul library history](https://culture.seoul.go.kr/culture/bbs/B0000001/view.do?menuNo=200050&nttId=8405&pageIndex=56): historic building use and restoration context.

Research photographs remain outside the model in `/tmp/seoul-city-hall-evidence/` for review; they are not published assets. The exact architect image URLs are:

| Local inspection file | Evidence | Original URL |
|---|---|---|
| `arch-30.jpg` | Southeast whole-building relationship, glass wave, angled historic wing | https://images.adsttc.com/media/images/52aa/5ebf/e8e4/4ee8/8f00/003e/large_jpg/cityhallct045.jpg?1386897066 |
| `arch-9.jpg` | East lens, S-shaped glass edge, triangle cladding | https://images.adsttc.com/media/images/52aa/5df1/e8e4/4e30/7c00/002f/large_jpg/cityhallct001.jpg?1386896859 |
| `arch-27.jpg` | West lens and historic roof garden | https://images.adsttc.com/media/images/52aa/5e85/e8e4/4ee8/8f00/003d/large_jpg/cityhallct040.jpg?1386897011 |
| `arch-31.jpg` | Side/rear cladding and office floors | https://images.adsttc.com/media/images/52aa/5ee1/e8e4/4e01/d100/0060/large_jpg/cityhallct050.jpg?1386897097 |
| `arch-52.jpg` | Ground-floor plan, relative building placement | https://images.adsttc.com/media/images/52aa/632f/e8e4/4e01/d100/0069/large_jpg/floor_(2).jpg?1386898218 |
| `arch-57.jpg` | S-shaped section and suspended occupied volume | https://images.adsttc.com/media/images/52aa/6350/e8e4/4ee8/8f00/0050/large_jpg/section.jpg?1386898252 |

The KMD 21-storey competition scheme is explicitly unbuilt and was excluded. Completion photos and drawings are historical references; current temporary advertising and exact interior furnishing are not reproduced.

## Existing model audit and concrete changes

The existing `reference-flight-seoul-city-hall` is a deliberately authored 115.66 × 101.75m compound with a 47.4m highest point. Its original game source used plan compression 0.4; the current adaptation reversed that factor in X/Z. The broad curved-glass idea is useful and retained, but its historic building is a centered rectangular wing, with an abbreviated 24m clock tower, and the two buildings share a simplified alignment. It also includes site scenery beyond the two buildings.

The replacement uses the source geographic U-shaped historic outline, angled east wing and northern west leg; the new building is placed northeast, not centered directly behind it. The glass shell is now a lofted S section with actual triangulated inner beams, two shallow faceted oval lenses, separate end cladding, a suspended pale upper volume, rear office structure and distinct roof fingers. The old building gets a separate source-shaped stone mass, vertical window rhythm, projecting central entrance, clock tablet, smaller lantern and patinated hip cap. The large artificial plaza/lawn is omitted; no neighboring building is removed to conceal a placement discrepancy.

## Location, height and ownership

Both GLBs use the same geographic anchor **126.978, 37.5665**. Blender axes are east X, north Y, up Z. The glTF exporter converts them to east X, up Y, south Z. The models are not recentered after export, so their offsets from the anchor carry the real relative placement. `source-footprints.json` records projected source geometry; the source database is read-only.

New building ownership (only two existing IDs):

- `c1e08f26-ebe0-4a95-827d-c617ca8b3d5f` — 서울특별시청, OSM `w198561926@28`.
- `bb10e1bc-1807-41fc-87c5-3bdac2090c9c` — its separately recorded glass/roof element, OSM `w768398467@5`.

Historic building ownership (one parent and all six existing child parts):

- `93725b2d-b39e-490f-bc2e-77536fc0d0c4` — 서울도서관, OSM `r10757525@8`.
- `34396137-6165-3238-B830-313064633537` — 19.5m outer/parapet outline.
- `39366536-6530-3761-A336-633966663466` — 18m main historic volume.
- `64653532-3632-3162-A430-656635303463` — 22m central volume.
- `61663761-3634-3437-B130-396663306134` — 30m lantern/roof envelope.
- `66386562-6237-3130-B832-613137653632` — 30–32m finial segment.
- `65353666-6637-3832-B737-653535376535` — 32–35m finial segment.

These historic heights are **OSM source-reported, unverified**, not official measurements. The new building has no usable metric height in the source DB or the official pages inspected; its approximately 47.4m nominal shell height is retained from the former authored model and checked visually against the published section. The exact steel spacing, material RGB values, lens curvature and internal structural member dimensions are photo-based estimates. They are not claimed to be measured fabrication information.

Reviewed assets: `bespoke-seoul-city-hall-new` and `bespoke-seoul-city-hall-library`. Both share fallback `reference-flight-seoul-city-hall`; each replaces only its own legacy generic parent. Their footprint sets are disjoint and their union is exactly the nine IDs already owned by the old compound. In particular, the historic library is explicitly modeled, not silently deleted, and its six children are not left as overlapping crude solids.

## Reproduction and review artifacts

Authoring source: `scripts/bespoke/seoul_city_hall.py`. Run through `scripts/bespoke/blender_mcp_client.py execute --port 9876 --script scripts/bespoke/seoul_city_hall.py`. The editable `.blend`, separate GLBs, common-origin recipe, bundle, real MCP call records and five review renders are staged under ignored `data/model-source/bespoke/seoul-city-hall/`.

The use of simple primitive helper functions does not determine the architecture: the source-specific geographic outline, lofted section, lens surfaces, diagonals and component positions are authored here for this site. No repeated residential facade generator is used.

## Accepted review and export validation

The second review corrected the white continuous upper strip into the western auditorium and eastern terraces, replaced the radial lens fan with faceted panel seams, separated pale fine mullions from dark alternating/crossed structural diagonals, and connected the clock tower through the notch in the adjacent 22m source part. The historic stone palette and stepped base/finial were also revised. The final rendered views were compared with the cited east, west and historic-front photographs; these are accepted as a photo-based interpretation with simplified windows/interiors and provisional material colors.

| Staged asset | Triangles | Meshes / materials | Highest exported point |
|---|---:|---:|---:|
| `bespoke-seoul-city-hall-new` | 57,292 | 27 / 14 | 48.22m including roof louvers |
| `bespoke-seoul-city-hall-library` | 28,424 | 18 / 10 | 35m including source-reported finial |

The new shell's nominal 47.4m is an author estimate; added roof louvers reach 48.22m. Neither is an official measured height. Both GLBs have minY=0, finite coordinates and normals, unit-normal error below 0.000001, and zero embedded images. Their nine footprint IDs are unique, disjoint between the two assets and identical in union to the previous compound's ownership.

After a successful MCP build, run `python3 scripts/bespoke/seoul_city_hall_finalize.py` to validate the export bytes and bind the completed MCP record SHA to `bundle.json`. The integration owner copies that exact record to `docs/model-audit/mcp/seoul-city-hall/build.json`; the artist's scripts do not publish or edit the shared manifests. `seoul_city_hall_viewport.py` frames the actual editable scene for the separate MCP screenshot record.
