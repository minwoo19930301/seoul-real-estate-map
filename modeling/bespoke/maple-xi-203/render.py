import bpy
from pathlib import Path
O=Path(__file__).parent;(O/'renders').mkdir(exist_ok=True)
for name in globals().get('REVIEW_VIEWS',['B_south_primary_match', 'A_east_primary_match', 'W41_North_end', 'W43_East_corner', 'Roof_three_individual_plants', 'Ground_NE_stone', 'Inner_L_core', 'SE_window_depth_detail']):
 s=bpy.context.scene;s.camera=bpy.data.objects[name];s.render.filepath=str(O/'renders'/f'{name}.png');bpy.ops.render.render(write_still=True);print('RENDERED203',name,flush=True)
print('203_BATCH_COMPLETE')
