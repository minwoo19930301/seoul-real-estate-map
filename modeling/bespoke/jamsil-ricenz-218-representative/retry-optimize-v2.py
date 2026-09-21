import bpy,pathlib
P=pathlib.Path(__file__).parent
old=bpy.data.scenes.get('Acro100_representative_revised');assert old
bpy.context.window.scene=old
for s in list(bpy.data.scenes):
 if s.name.startswith('Jamsil Ricenz218 representative'):
  bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
p=P/'optimize-v2.py';exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
