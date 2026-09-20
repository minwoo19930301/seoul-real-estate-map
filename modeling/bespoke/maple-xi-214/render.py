import bpy
from pathlib import Path
O=Path(__file__).parent;(O/'renders').mkdir(exist_ok=True)
for name in globals().get('REVIEW_VIEWS',['A_SE_primary_match','W05_north_coplanar_end','NE_end_detail','NW_core_courtyard','Roof_two_individual_plants','Ground_north_stone','SW_unverified_return','SE_primary_detail']):
 s=bpy.context.scene;s.camera=bpy.data.objects[name];s.render.filepath=str(O/'renders'/f'{name}.png');bpy.ops.render.render(write_still=True);print('RENDERED214',name,flush=True)
print('214_BATCH_COMPLETE')
