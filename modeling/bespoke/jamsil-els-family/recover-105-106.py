import bpy,pathlib
P=pathlib.Path(__file__).parent
s=bpy.data.scenes.get('Jamsil Els106 representative')
if s:
 bpy.context.window.scene=bpy.data.scenes['Acro100_representative_revised'];bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
for t,scripts in [(105,['check-standalone.py']),(106,['build.py','check-standalone.py'])]:
 for script in scripts:
  p=P/str(t)/script;exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
