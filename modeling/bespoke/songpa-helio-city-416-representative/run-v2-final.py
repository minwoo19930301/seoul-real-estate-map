import pathlib,bpy
P=pathlib.Path(__file__).parent
for sc in list(bpy.data.scenes):
 if sc.name.startswith('Songpa Helio416 representative'):
  bpy.context.window.scene=bpy.data.scenes['Acro100_representative_revised'];bpy.data.batch_remove(ids=list(sc.objects));bpy.data.scenes.remove(sc)
for name in ['build.py','check-standalone.py']:
 p=P/name;exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
