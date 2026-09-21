# Coarse representative apartment models

These photo-informed models reuse one or two coarse forms per complex. They do
not earn strict bespoke completion credit. Existing authored models, manifests,
and footprint ownership are protected. The runtime reads a separate optional
`public/models/representative-manifest.json`; failed manifest or GLB loads retain
existing buildings. Generic compound geometry yields only after a replacement
actually draws, leaving unrelated solid footprints visible.

## Bundle and review

Stage each bundle under `data/model-source/representative-batch01/<site>/`.
A bundle has `siteId`, `constructionMethod: "representative-photo-informed"`,
`sources`, `mcpEvidence`, `assets`, `expectedFootprintIds`, and optional `recipeFiles`.
`expectedFootprintIds` must contain the complete selected source compound footprint
set; it must exactly equal the union owned by the assets. Do not omit records just
because geometry or a tower model is missing. Other batches may use
`representative-batchNN/` or `representative/` staging roots.
Each source has a unique `id`, HTTP `url`, bundle-relative `inputFile` (captured
source evidence), and its `sha256`. MCP evidence uses the existing committed
`docs/model-audit/mcp/` JSON transcript format, including a successful actual
`execute_blender_code` response and its hash. Never manufacture a transcript.

Each asset has `id`, `file` (GLB), `blendSource`, `nameKo`, `coordinate: {lon,lat}`,
`footprintIds`, empty `supersedes`, `referenceUrl`, `representativeForms` (1 or 2),
and nonempty `uncertainties`. Blender geometry must be local metres, ground zero,
with +X east / +Y up / +Z south after GLB normalization. Its coordinate is the
same surveyed origin used to construct all local tower offsets, not an arbitrary
search point. Footprint IDs must be actual source IDs reviewed by the operator;
numeric validation cannot prove a surveyed anchor or ownership is correct.

The independent review has matching `siteId`, `status: "coarse-visually-reviewed"`,
`comparisons: [{sourceId, observation}]` for every source, at least two `views`
describing reviewed renders, and `limitations`. `reviewedInputs` maps every GLB,
blend, source input and recipe filename to its SHA-256. Review photographs,
placement and renders before writing this record; hashes are integrity evidence,
not proof of visual accuracy. Do not use the strict bespoke review status.

## Validate, install, recover

```
python3 scripts/publish_representative_models.py path/to/bundle.json --review path/to/review.json
python3 scripts/publish_representative_models.py path/to/bundle.json --review path/to/review.json --publish
python3 -m unittest discover -s tests -p 'test_*publisher.py'
node --experimental-strip-types --test tests/representative-models.test.mjs tests/reference-models.test.mjs
```

The first command writes no published files. Installation appends assets to the
separate manifest, copies GLBs/editable blends/recipes, records coarse review in
`docs/model-audit/published-representative.json`, and updates deployment hashes.
Source photos remain local unless separately cleared for redistribution.
All destination bytes are staged before replacement; ordinary failures roll back.
Process termination/power loss is not a filesystem transaction: inspect the
manifest, audit, deployment hashes and copied assets before retrying. Existing
IDs and footprints reject duplicate retries rather than silently overwriting.
For an intentional replacement, explicitly review/removal of the prior
representative entry and deployment record is needed; the script is append-only.
Never remove bespoke assets to make a representative bundle pass validation.
