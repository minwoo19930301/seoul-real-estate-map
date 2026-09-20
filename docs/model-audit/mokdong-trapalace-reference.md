# 목동 트라팰리스 — individual exterior reconstruction

Photo-reviewed exterior reconstruction; not a measured BIM or cadastral replacement. 2026-09-21 research.

## Eligibility and identity

Official Seoul apartment queue (OA-15818 and K-apt weekly) gives one management code **A15870101**, 522 households and four residential towers at 299 Omok-ro. Samsung C&T's official sales archive independently states 522 households and January 2009 occupancy. The public building register splits this into **Mok-dong962 Western Avenue:264 households** and **962-1 Eastern Avenue:258 households**. Neither physical half alone is claimed to exceed400; the official managed complex does. Four towers are WesternA/B and EasternA/B, not invented101–104.

Numbered siteplan `K2004014_E.jpg`, hosted on local district archive mokdong.com, explicitly labels WestA49F,WestB42F,EastA48F,EastB41F. Its original publishing architect and issue date are not independently verified. It is a secondary-hosted architectural drawing, not a surveyed as-built CAD. SIAPLAN's own project page and five actual completed photographs supply primary exterior evidence. The 4-tu.jpg image in the local archive is CG and is not used as as-built material evidence.

## Independent anchors and geometry

Four named OSM-source building polygons supply individual WGS84 centroids. The coarse sources are nearly simple rectangles; the authored profiles instead trace the numbered plan's diagonal floorplates and narrow rear projections. A four-point affine fit of approximate plan body-centres to the corresponding named source centroids gives residuals1.95–1.97m. These are unsurveyed mapping controls, not four field-measured points. Each asset retains its exact source centroid and the affine transform is used only for local authored geometry. Plan north and adjoining Omok-ro orientation are consistent with site map.

- WestA: b560f468-8338-4129-8897-594d06024307
- WestB: eb763d30-2a31-4b0a-b77c-2bb753b9d5d4
- EastA: f48046f3-fc57-44db-9f1d-a228ab5c688f
- EastB: 9bed6662-0c52-4337-abdd-cd0e22788406
- Separate west8F retail: c097c940-ce51-4c9f-bd7f-58cd6c23dcef
- Separate east8F retail: f56285fc-1765-405a-82a8-c9fa8c5aa491

Existing legacy apt-a15870101 owns exactly the four residential sourceIDs. All five new assets share this explicit supersession, allowing a complete compound fallback. No prior authored reference or bespoke asset for this site was found. Neither retail source has another legacy GLB owner in footprint-matches; nearby lazy survey tiles contain no explicit owner for these sixIDs. The nearby HyperionII, broadcasting hall and unrelated buildings remain outside ownership.

## Height datums

|Tower|Storeys|CVU architectural/helipad m|CVU highest occupied m|Local register m|
|---|---:|---:|---:|---:|
|WesternA|49|185.7|164.2|174.17 for the wholeWestern record|
|WesternB|42|162.8|143.0|not separately listed|
|EasternA|48|182.5|161.0|170.99 for the wholeEastern record|
|EasternB|41|159.6|139.8|not separately listed|

CVU/CTBUH detail pages provide explicit architectural and helipad top values. They supersede rounded/unverified OSM heights for this visual reconstruction. Register values are preserved rather than called errors: legal height datum and inclusion of roof structures differ and are not fully reconciled. Intermediate main-terrace, penthouse and storey levels are photo-based interpretation, not independent survey. Ring railing tops are within0.04m of the adopted architectural envelope. The two bridges are interpreted at34F, approximately114m on both sides (photo/floor interpolation estimate, not a surveyed deck elevation); exact deck survey is unavailable. The photographed/formally reported5m bridge width is used, with the two site-appropriate spans derived from anchors.

## What is actually modeled

All four towers have their own anchors, storey count, total height, distinct neighboring bridge relation and roof level. The plan actually repeats the same four related diamond forms; their shared details are intentionally derived from that documented site, not seeded citywide templates. The separate assets include pale structural piers with paired bluegreen windows and recessed opening panes, upper continuous glazed banks replacing lower stone spandrels, two staggered penthouse volumes, open roof frames, strong high-corner stone piers, and the circular ring around a central diamond helipad with radial underside members. Each A asset carries its corresponding enclosed34F steel-braced bridge to B.

Commercial fronts retain their existing distinct source outlines and eight-storey division, with a deliberately simplified reddish stone/glass facade. The parking wings are simplified and the central public walking street stays open. No retail tenant signs, private interiors or detailed landscaping are claimed.

## Known limits

The opposite lower facade and exact rear-service-window arrangement have fewer direct views. Fine window and pier widths, guardrails, helipad understructure, roof plant, retail entrances and intermediate height divisions are inferred from the provided photographs. The external stair at the top is omitted rather than invented from insufficient detail. No claim of all-Seoul completion, exact architectural CAD or perfect photo correspondence is made. The source photos remain reference-only and are not embedded as textures or redistributed inside model sources.

## Rebuild and proof

The stage is self-contained for geometry: `build.py` reads only `recipe.json` and Blender's standard Python modules. It resets its Blender scene, emits each local anchored GLB, assembles the editable site scene, then saves mokdong-trapalace.blend and bundle.json. `prepare.py` reconstructs recipe from preserved source-buildings.json and explicit authored plan pixel coordinates; it requires numpy/shapely but no DB or network. RealMCP execution and rendering records are separate files. `render-v3.py` renders the seven saved comparison cameras; `validate.py` checks finite GLB data, baked node transforms, unit normals, metre bounds, minY0, absent image textures and six unique owned sourceIDs.

Use only an isolated scene/instance: `blender_mcp_client.py execute --port 9877 --script <stage>/build.py --record <stage>/mcp-build.json`. Open the saved .blend directly to inspect/edit the existing authored mesh, without recreating external research downloads.
