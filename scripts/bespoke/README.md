# Individual Blender reconstruction

Each site has its own authored script, editable Blender scene, real-world references, and visual comparison. Shared helpers below only execute MCP calls, normalize GLB encoding, and publish verified files. They do not invent building shapes, colors or facades.

The reviewed models use Blender 4.5.11 LTS and [mcp-for-blender](https://github.com/ahujasid/mcp-for-blender) revision `6f992ffbca3cb715d111fc640b737b808632273c`. Install the server in a separate environment and use the addon from the same revision. The authoring sessions were independent GUI instances on localhost ports 9876, 9877 and 9878; no global app configuration was changed.

```sh
git clone https://github.com/ahujasid/mcp-for-blender.git /tmp/seoul-blender-mcp
git -C /tmp/seoul-blender-mcp checkout 6f992ffbca3cb715d111fc640b737b808632273c
uv venv /tmp/seoul-blender-mcp-env
uv pip install --python /tmp/seoul-blender-mcp-env/bin/python /tmp/seoul-blender-mcp
python3 scripts/bespoke/launch_blender.py --addon /tmp/seoul-blender-mcp/addon.py --port 9876
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py inspect --port 9876
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute --port 9876 --script scripts/bespoke/express_terminal.py
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py screenshot --port 9876 --output /tmp/terminal-viewport.png
```

The pinned upstream has a missing optional `blender_mcp.config` module in `get_addon_status`. This diagnostic reports an error; the live `get_scene_info`, `execute_blender_code`, and viewport tools are verified independently. Telemetry is disabled by the client environment. Construction records include the actual MCP calls, and Blender version is read inside the live instance.

Before publishing, compare multiple views to the cited photographs and plans. Record observed changes and remaining estimates in a site-specific review JSON. The publisher requires that record, normalizes node transforms without moving the geographic anchor, saves editable `.blend` files under `modeling/bespoke/`, and writes a separate replacement manifest. A new model only suppresses an old one after a successful draw; load failures retain the previous representation.

The complete model inventory is a review backlog. Unique filenames, hashes, source footprints and triangle counts do not establish visual likeness. Only reviewed site reconstructions count as completed work.

## Frozen scope and recovery

The first two batches contain **8 reviewed physical sites and 27 GLBs**: terminal1, SKY-L65 four towers, Banpo/Jamsu1, Hyperion five components, Seoul2841, Maple208–213 six towers, Tower Palace A–G seven towers, and City Hall new/library two buildings. The current inventory and later additions are listed in [the model audit](../../docs/model-audit/README.md). This is not a claim that every Seoul building or every apartment has been rebuilt to this standard. The remainder stays in the review backlog.

The committed `.blend` files under `modeling/bespoke/` are the editable recovery source. The runtime assets are in `public/models/bespoke/`; geographic anchors, component names, source ownership and uncertainties are in `public/models/bespoke-manifest.json`. The reviewed input hashes and comparisons are in `docs/model-audit/published-bespoke.json`. Inspect those records together rather than assuming a newly exported file is the reviewed file.

`data/model-source/bespoke/` is an **ignored authoring workspace**, not a directory supplied by a fresh checkout. Local `bundle.json`, GLB exports, screenshots and MCP transcripts may be absent. Their old absolute paths are not portable. Reference photographs downloaded under `/tmp` are deliberately not committed; source URLs can change or disappear. No single command recreates all original downloads, unpublished preparation data, visual reviews and publisher inputs.

Restore a working copy of the committed inputs and editable scenes from the repository root:

```sh
python3 - <<'PY'
from pathlib import Path
import shutil
source = Path('modeling/bespoke')
stage = Path('data/model-source/bespoke')
for folder in source.iterdir():
    if not folder.is_dir():
        continue
    aliases = {'seoul-express-terminal-gyeongbu-yeongdong': 'express-terminal',
               'lg-art-center-seoul': 'lg-art-center'}
    name = aliases.get(folder.name, folder.name)
    target = stage / name
    target.mkdir(parents=True, exist_ok=True)
    for file in folder.iterdir():
        if file.suffix in {'.blend', '.json', '.geojson'}:
            destination = target / file.name
            if not destination.exists():
                shutil.copy2(file, destination)
PY
```

Open the desired working-copy `.blend` in an isolated Blender instance. With MCP, make file opening a **separate execute call** before running an export or render script; opening a file and immediately exporting in the same call can leave Blender's context invalid. Render helper scripts use the currently open scene and require its named cameras. They do not load the scene for you. Make sure the target staging directory exists first.

For a manual export, select only the component meshes named by that asset's manifest record. Exclude review ground, lights, cameras and other site assets. Export glTF Binary with Y-up and applied transforms. Retain metres and the asset's geographic anchor: **do not recenter by bounding-box centre**. SKY, Hyperion and Maple saved scenes place individually exported pieces together for inspection. Undo only the per-asset assembly translation recorded by `siteEN` or the Maple anchor-offset calculation before exporting an individual piece; preserve its geometry and orientation. `normalize_glb.mjs` bakes node transforms but does not repair a wrong origin. Check minimum Y0 and metre bounds after export.

## Site-specific regeneration

The scripts below run inside Blender through the MCP client unless marked as preparation. Most builders replace the current scene, so use the isolated authoring instance. Geometry generation is separate from visual approval and publication.

| Site / committed scene folder | Construction and inputs | Recovery limits |
|---|---|---|
| `seoul-express-terminal-gyeongbu-yeongdong` | `express_terminal.py`; authored measurements and components are in the script. Outputs to staging `express-terminal/`. | `express_terminal_render.py` and validation require the terminal scene. Reference images are external. |
| `skyl65` | `skyl65_blender.py` reads staging `recipe-input.json`, with fallback to the committed recipe. `claimed-source-buildings.json` preserves the source geometries. | Optional `skyl65_prepare.py` uses NumPy/Shapely and the preserved source records to reconstruct the manual trace. Original brochure/photo downloads are not inputs supplied by the checkout. Prefer the frozen recipe when reproducing the reviewed model. |
| `hyperion` | `hyperion_blender.py` rebuilds only the three towers and parking podium. `hyperion_department_blender.py` then appends the separate department store using `department-recipe.json` and the first script's mesh helpers. | After the first builder, keep/open staging `hyperion-authored.blend`, then run the department builder in a subsequent MCP call. It requires staging `bundle.json`, created by the first builder. The committed final scene already contains all five assets; do not mistake a four-asset rebuild for the final result. |
| `banpo-jamsu` | `banpo_jamsu.py` uses committed `public/bridge-outlines.geojson`, specifically `osm:way/1085504592`. Saved `recipe.json` records the authored parameters; the builder writes it rather than reading it. | Builder creates GLB, scene and recipe, **not a complete publishing bundle**. Recover reviewed metadata from the manifest/audit record and construct a fresh staging bundle for publication. |
| `culture-station-seoul284` | `culture_station_seoul284.py`; dimensions, separate wings and facade details are authored in the script. | Render and validation helpers expect the matching scene. Historical plan/photo files used for comparison are external. |
| `maple-club-cloud` | Copy committed `authored-input.json` into staging, then run `maple_club_cloud_blender.py`. This constructs only210/211 and the connector owned by210. | Builder reads the staging input without a committed-path fallback. Optional `maple_club_cloud_prepare.py` derives it from `docs/MAPLE_XI_MODEL_RECIPE.json` with NumPy/Shapely; earlier full-complex source acquisition is not an automatic prerequisite workflow included here. Other Maple models remain unchanged. |
| `tower-palace` | `tower_palace_blender.py` reads the frozen `recipe-input.json`, with a committed-path fallback, and exports A–G at their individual anchors. | The combined scene uses assembly offsets recorded in the recipe; retain per-tower origins when exporting. The preparation script can recreate a trace, but does not replace the reviewed face assignments. |
| `seoul-city-hall` | Restore `source-footprints.json`, then run `seoul_city_hall.py`; after the MCP call returns, run `seoul_city_hall_finalize.py` with regular Python to validate and bind the transcript. | Two assets share the retained geographic origin. The new and historic buildings divide nine source IDs. Finalization validates files; it does not approve architectural likeness. |
| `maple-next-towers` | Restore `authored-input.json`, then run `maple_next_blender.py`. It builds only208/209/212/213. | The staged recipe contains face-specific assignments and unequal roof tiers; do not substitute the full-complex template. Review/render helpers require the matching scene. |
| `jungmyeongjeon` | Restore `recipe-input.json` and `source-footprint.json`, then run `jungmyeongjeon.py` through MCP. Render with `jungmyeongjeon_render.py`; validate with regular Python `jungmyeongjeon_validate.py`. | Restoration drawing dimensions and photographed post-restoration details are distinct from the larger retained source outline. Reference photographs and the restoration PDF remain external. |
| `mmca-deoksugung` | Restore `authored-input.json` and `source-footprint.json`, then run `mmca_deoksugung_blender.py` through MCP and the matching render helper. | Only the west museum wing is included. The adjoining east Seokjojeon, connecting passage and fountain remain separate. Wing roof covers and rear openings are explicitly provisional. |
| `lg-art-center-seoul` | Restore inputs into staging `lg-art-center/` using the alias above; run `lg_art_center_blender.py` through MCP. | A single source footprint includes both the Arts Center and Discovery Lab. The authoring folder and published site ID differ. Optional research preparation requires external architect/operator sources; use the frozen authored input for recovery. |

For example, after restoring inputs, a fresh Hyperion construction requires two separate calls:

```sh
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute \
  --port 9877 --script scripts/bespoke/hyperion_blender.py \
  --record data/model-source/bespoke/hyperion/mcp-build.json
/tmp/seoul-blender-mcp-env/bin/python scripts/bespoke/blender_mcp_client.py execute \
  --port 9877 --script scripts/bespoke/hyperion_department_blender.py \
  --record data/model-source/bespoke/hyperion/mcp-department-build.json
```

Optional preparation scripts can overwrite frozen recipes and omit later review metadata. Rebuilding geometry also regenerates bundles and may omit integration-time ownership or replacement corrections. Reconcile the resulting asset IDs, coordinates, `footprintIds`, `supersedes`, categories and source limitations with the committed manifest before publication. In particular, the Hyperion department store alone owns its department-store footprint; the erroneous69-floor survey model is an explicit invalid-height replacement, not an extra residential tower.

Keep new renders and MCP evidence, compare them to the cited primary sources, and create a fresh review record whose `reviewedInputs` hashes match the new GLB and `.blend` bytes. Reconstruct missing staging bundle paths relative to that workspace. Do not reuse an old visual approval merely because a script finished. Blender/exporter versions or datablock names can change file hashes; matching shape must still be checked visually. The publisher validates the new reviewed inputs and stages publication atomically; it does not perform the architectural comparison itself.
