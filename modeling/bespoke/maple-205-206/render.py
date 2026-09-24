import bpy
from pathlib import Path
O=Path(__file__).parent;NUMBER=int(bpy.data.filepath.split('maple-')[-1].split('.')[0]);out=O/f'renders-{NUMBER}';out.mkdir(exist_ok=True)
for name in globals().get('REVIEW_VIEWS',['South_family','North_core','NE_street','West_glass','Roof_support','Window_depth']):
 s=bpy.context.scene;s.camera=bpy.data.objects[name];s.render.filepath=str(out/f'{name}.png');bpy.ops.render.render(write_still=True);print('RENDERED',NUMBER,name,flush=True)
