import bpy,json
from pathlib import Path
O=Path(__file__).parent
n=int(bpy.data.filepath.split('maple-')[-1].split('.')[0])
s=bpy.context.scene
for name in ['Street','Roof','Opposite','Close']:
 s.camera=bpy.data.objects[name];s.render.filepath=str(O/f'{n}-{name.lower()}.png');bpy.ops.render.render(write_still=True)
print('RENDER_PASS',n)
