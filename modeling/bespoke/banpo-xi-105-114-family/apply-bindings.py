import bpy,pathlib,json,hashlib
P=pathlib.Path(__file__).parent;old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};reports=[]
for t in map(str,range(105,115)):
 p=P/t;D=json.loads((p/'source-data.json').read_text());file=p/('banpo-xi-'+t+'-authored.blend')
 with bpy.data.libraries.load(str(file),link=False) as (a,b):b.scenes=a.scenes
 s=b.scenes[0];s['supersedesAssetIds']=json.dumps(D['supersedesAssetIds']);s['binding_status']=D['binding_status'];bpy.data.libraries.write(str(file),{s},fake_user=True,compress=True);bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
after={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after and old==bpy.context.scene
exec(compile((P/'check-standalone.py').read_text(),str(P/'check-standalone.py'),'exec'),{'__file__':str(P/'check-standalone.py')})
