# Apartment modeling workflow

- Delegate source, building identity, and reference photograph research to `gpt-5.6-luna` with `low` reasoning effort.
- Delegate actual Blender modeling to `gpt-6-astra` with `low` reasoning effort, using the existing Blender MCP connection. Do not launch another Blender process, application, or window.
- Research agents should work in the ignored `data/model-source/bespoke/` staging area. Keep original reference photographs local; do not commit or embed them in models.
- Verify photographs against their actual source page and inspect the images. Record which building numbers are visible. A complex photograph does not verify every individual facade.
- Research and model only ONE representative building per apartment complex. Once approved, duplicate or instance that same model for the other buildings. Do not rebuild, independently research, render four views, or manually inspect every sibling. A separately authored Blender file or GLB for every sibling is not the requested workflow.
- Use the existing building inventory for sibling positions, orientation and optional size/height transforms. Share the representative geometry and materials. Remove the representative's building number from clones. Record that the repeated shape/facade is inferred, including differences from the actual footprint or floor layout; do not claim individual reconstruction or exact footprint preservation for a transformed clone.
- Review front, opposite, side and roof renders for the representative once. For the duplicate batch, run automated identity/transform/fallback checks and sample the integrated map; escalate only actual exceptions. Preserve existing footprint ownership and unrelated buildings.
- When following the current usage goal, read the user's displayed REMAINING weekly allowance: stop starting new work when remaining allowance reaches 40% (60% used). Report remaining and used separately.
- Preserve previously published model files and metadata. A replacement with changed geometry needs a new asset identity; do not silently overwrite the archived model.
- Report local validation, commit, PR, merge, and deployment separately. A PR upload does not establish deployment or completion of all Seoul apartments.
