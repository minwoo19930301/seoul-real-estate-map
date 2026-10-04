# Four apartment complexes: representative models and shared copies

This batch models DMC Raemian e-Pyeonhansesang (50 of 51 buildings), Gwanak Dream Town (31 of 44), Lake Palace (29 of 35), and Dogok Rexle (25 of 34). Total: 135 building placements, four authored representatives and 131 literal shared-geometry/material instances. All four remain partial inventory coverage, not completed complexes.

## Reference scope

DMC205 and Gwanak111 are identifiable in the local reference photographs. Lake107 uses complex photographs showing103/101; Dogok209 uses a photograph showing102. The latter two are explicitly complex-photo inferences, not photographs verifying those representative buildings. Hidden faces, roof detail, and sibling shapes/floor layouts are inferred. Original reference photographs stay local and are neither committed nor embedded as textures.

Representatives retain their source footprints and registered heights. Clones reuse the same geometry/materials and use inventory position/orientation and registered-height transforms; their geometry is not an exact reconstruction of each sibling footprint. Four views are reviewed once per representative.

## Inventory and fallback preservation

DMC501 and Lake101 were recovered with matching local source footprints and unique registered residential identities. DMC309 remains missing. Lake117/118/119/120/134/135 remain missing. Gwanak has13 unmatched source footprints. Dogok101/102/103 have possible source geometry but no existing fallback asset ownership and are not added here; six additional source footprints remain unresolved.

Compound fallback meshes were partitioned with frozen provenance and unrelated source members retained. Historical hull approximations in the fallback sources remain identified as approximations. The original archived models are preserved. Browser checks exercise normal loading, representative GLB failure, and both representative/fallback failure, including restored raw building display.

## Execution

Blender MCP runs through the upstream MCP server and safe-mode addon in an existing headless Blender process. No visible application/window is opened. Authoring, four-view rendering, GLB export, saved-file reload and workspace restoration are recorded in the corresponding MCP evidence files. New model generation is confined to one representative per complex.

## Validation

All four browser families passed all three cases (12 checks). Node tests: 13,910 passed. Apartment queue Python tests: 18 passed. Shared-instance placement checks found no source-body neighbor or copy-to-copy overlaps. Production TypeScript/Vite build passed in44.34s, with the existing oversized-chunk warning.

The regenerated queue records36 completed management codes out of1,417 eligible codes and1,097 representative-inferred building placements. These four partial complexes do not increase the completed-complex count. PR upload, merge and deployment are separate states.
