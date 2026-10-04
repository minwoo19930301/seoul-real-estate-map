import bpy,pathlib
P=pathlib.Path(__file__).parent
s=bpy.data.scenes.get('Acro Riverview Shinbanpo101 representative')
if s:
 bpy.context.window.scene=bpy.data.scenes['Acro100_representative_revised'];bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
p=P/'build.py';exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
