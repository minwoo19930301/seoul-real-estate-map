# Apartment modeling workflow

- Delegate source, building identity, and reference photograph research to `gpt-5.6-luna` with `low` reasoning effort.
- Delegate actual Blender modeling to `gpt-6-astra` with `low` reasoning effort, using the existing Blender MCP connection. Do not launch another Blender process, application, or window.
- Research agents should work in the ignored `data/model-source/bespoke/` staging area. Keep original reference photographs local; do not commit or embed them in models.
- Verify photographs against their actual source page and inspect the images. Record which building numbers are visible. A complex photograph does not verify every individual facade.
- After a representative model passes visual review, its exterior design may be inferred onto other buildings in the same complex. Preserve each building's own source polygon, registered height and floors, number, and fallback ownership. Record the inference and unresolved facts.
- Inspect final front, opposite, side, and roof renders. Independently check exported geometry, concave roofs, adjoining building overlaps, and browser fallback behavior before publication.
- Preserve previously published model files and metadata. A replacement with changed geometry needs a new asset identity; do not silently overwrite the archived model.
- Report local validation, commit, PR, merge, and deployment separately. A PR upload does not establish deployment or completion of all Seoul apartments.
