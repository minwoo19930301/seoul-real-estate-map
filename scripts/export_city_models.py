"""Blender background re-export from the preserved, unmodified landmark master.

blender --background data/model-source/seoul-landmarks.blend --python scripts/export_city_models.py
"""
from pathlib import Path
import hashlib
import json
import bpy

root = Path(__file__).resolve().parents[1]
expected = {'sixtythree', 'lotte', 'nseoul', 'coex'}
destination = root / 'data/model-source/reexport-2026-09-09'
destination.mkdir(parents=True, exist_ok=True)
if bpy.context.scene.name != 'Seoul Landmark Asset Studio':
    raise RuntimeError('Unexpected master scene')
results = []
for identifier in sorted(expected):
    bpy.ops.object.select_all(action='DESELECT')
    collection = bpy.data.collections['LANDMARK_' + identifier]
    collection.hide_viewport = False
    for obj in collection.objects:
        obj.hide_set(False)
        obj.select_set(True)
    bpy.context.view_layer.objects.active = bpy.data.objects[identifier + '_root']
    output = destination / (identifier + '.glb')
    result = bpy.ops.export_scene.gltf(filepath=str(output), export_format='GLB',
        use_selection=True, export_yup=True, export_apply=False, export_extras=True,
        export_animations=False, export_cameras=False, export_lights=False,
        export_materials='EXPORT', export_texcoords=False, export_normals=True)
    if 'FINISHED' not in result:
        raise RuntimeError('Export failed: ' + identifier)
    digest = hashlib.sha256(output.read_bytes()).hexdigest()
    shipped = root / 'public/models' / output.name
    results.append({'id': identifier, 'sha256': digest, 'bytes': output.stat().st_size,
                    'matches_shipped_glb': digest == hashlib.sha256(shipped.read_bytes()).hexdigest()})
proof = {'blender': bpy.app.version_string, 'master_sha256': hashlib.sha256(Path(bpy.data.filepath).read_bytes()).hexdigest(),
         'master_modified': False, 'units': 'metres, glTF Y-up, floor-centred', 'results': results}
(destination / 'proof.json').write_text(json.dumps(proof, indent=2) + '\n')
print(json.dumps(proof))
