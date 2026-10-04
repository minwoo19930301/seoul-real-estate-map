import bpy,pathlib,json
P=pathlib.Path(__file__).parent;old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes}
for t in map(str,range(142,145)):
 p=P/t/'build.py';exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after and bpy.context.scene==old
(P/'scene-preservation-batch-5.json').write_text(json.dumps({'equal':before==after,'active_scene':old.name,'before':before,'after':after},indent=2))
