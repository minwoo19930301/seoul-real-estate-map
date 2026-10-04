import bpy,json,pathlib,hashlib
P=pathlib.Path(__file__).parent;old=bpy.context.scene
files=[P/'bespoke-raemian-prestige-101.glb']+[P/(v+'.png') for v in ['front','opposite','side','roof']]
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
before={p.name:sha(p) for p in files}
blend=P/'bespoke-raemian-prestige-101-authored.blend'
with bpy.data.libraries.load(str(blend),link=False) as (a,b):
 assert len(a.scenes)==1;b.scenes=a.scenes
s=b.scenes[0];previous=s['supersedes'];s['supersedes']='residential-2541ff4f-21d3-4ea5-8250-7d0950910d90'
bpy.data.libraries.write(str(blend),{s},fake_user=True,compress=True)
bpy.data.scenes.remove(s)
with bpy.data.libraries.load(str(blend),link=False) as (a,b):
 assert len(a.scenes)==1;b.scenes=a.scenes
s=b.scenes[0];assert s['supersedes']=='residential-2541ff4f-21d3-4ea5-8250-7d0950910d90'
after={p.name:sha(p) for p in files};assert before==after and bpy.context.scene==old
r={'previous_supersedes':previous,'supersedes':s['supersedes'],'unchanged_glb_and_views':before,'blend_sha256':sha(blend),'reloaded_property_verified':True,'prior_scene_restored':True,'passed':True}
bpy.data.scenes.remove(s);(P/'metadata-correction-validation.json').write_text(json.dumps(r,indent=2));print(json.dumps(r))
exec(compile((P/'validate_blend.py').read_text(),str(P/'validate_blend.py'),'exec'))
