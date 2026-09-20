# Galleria Palace review stage

Four isolated Blender-made exports: A, B, C residential towers with mixed uses unresolved, and a separate common lower-wing model. Official apartment management scope is A13822301, 741 households, three buildings. Five visible tower lobes do not mean five management buildings.

Primary completed-building references are HeeRim photographs `heerim-21.jpg` and `heerim-23.jpg`. The source registry joint row is 46F/149.4m with no tower letter; 1,584 in that row is **not** used as an apartment count or a sum. Source floor-by-floor apartment/officetel classification is unverified.

The republished roof plan's 36/40/46 level labels disagree with the post-completion CODIL report and photos. Its location/orientation are used, but conflicting labels are not presented as built dimensions. A numbered 30th-floor appraisal diagram identifies A's northwest double-lobe footprint; the remaining B/C letter mapping follows the uniquely matching four/eight apartment-line plans and location, with that inference recorded.

The C west upper end was initially mistaken for the small north projection. Camera-to-source-vertex projection disproved this; the final photographed southwest face is source edge 18–19. Its upper approximately six storeys have thin glazed mullions; the adjacent cantilever beams are approximately 4.6m lower than the 149.4m glass top. This is a photo estimate, not a measured roof drawing.

Editable .blend has named building/component collections. Export copies batch those surfaces into one mesh per GLB with materials preserved. No source image textures or neighboring buildings are embedded. No ground/landscape sheet covers map roads.

Common lower wings deliberately own **no** source footprint IDs: their source parents have `extrude=0` and `has_parts=1`, and claiming them would hide tower children when a tower fails. Each of A/B/C claims one exact child source ID. Parent IDs are evidence only, while the standalone east service building and eastern large neighbor remain unclaimed.

`build.py` reads only `authored-input.json` beside itself and executes through actual isolated Blender MCP on port 9876. `render_reviews.py` produces six ground/roof views. `validate_glbs.py` checks actual GLB data. `check_roof_supports.py` runs real Blender BVH rays, checking 12 seated supports and four genuinely open louver assemblies.
