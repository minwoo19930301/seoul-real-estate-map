import bpy
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/banpo-jamsu'
scene=bpy.context.scene
scene.render.engine='CYCLES';scene.cycles.samples=20
scene.world.use_nodes=True;scene.world.node_tree.nodes['Background'].inputs[0].default_value=(.70,.76,.79,1);scene.world.node_tree.nodes['Background'].inputs[1].default_value=.8
for name in ['Overview','Navigation_side','Underdeck']:
 scene.camera=bpy.data.objects[name];scene.camera.data.clip_end=5000;scene.render.filepath=str(OUT/(name.lower()+'.png'));bpy.ops.render.render(write_still=True)
scene.camera=bpy.data.objects['Navigation_side']
bpy.ops.wm.save_as_mainfile(filepath=str(OUT/'banpo-jamsu.blend'))
print('THREE_REVIEW_RENDERS_COMPLETE')
