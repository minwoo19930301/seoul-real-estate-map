import bpy,json,pathlib,hashlib,runpy
old=bpy.context.scene
before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes}
JOBS=[{'n': 101, 'p': '/Users/hyemini/Documents/Codex/2026-09-21/seoul-real-estate-map/data/model-source/bespoke/acro-riverview-101-representative', 'sha': '576bf05fbc20169bfd459ac65351c202809b794a74e83c478aaf4fa0d5317ed2', 'supersedes': ['fallback-acro-riverview-101']}, {'n': 102, 'p': '/Users/hyemini/Documents/Codex/2026-09-21/seoul-real-estate-map/data/model-source/bespoke/acro-riverview-102-105-family/102', 'sha': '538412e355d0d328d570a2472f935b5cf73c6eb3649e920b63673f1e06cd1c2e', 'supersedes': ['fallback-acro-riverview-102']}, {'n': 103, 'p': '/Users/hyemini/Documents/Codex/2026-09-21/seoul-real-estate-map/data/model-source/bespoke/acro-riverview-102-105-family/103', 'sha': 'b69056f716705141c12829d5eb5c629f11c847ec57da072ce184070019adce37', 'supersedes': ['fallback-acro-riverview-103']}, {'n': 104, 'p': '/Users/hyemini/Documents/Codex/2026-09-21/seoul-real-estate-map/data/model-source/bespoke/acro-riverview-102-105-family/104', 'sha': '495ff65db53bf4ed71098193130dd8d1fc53d08977f9cad8c7251c7481a37e2f', 'supersedes': ['fallback-acro-riverview-104']}, {'n': 105, 'p': '/Users/hyemini/Documents/Codex/2026-09-21/seoul-real-estate-map/data/model-source/bespoke/acro-riverview-102-105-family/105', 'sha': '2d9604dee637e5934adc2afa42f0ff98c59924b7010fb281a2372d42d481a83f', 'supersedes': ['fallback-acro-riverview-105']}]
results=[]
for j in JOBS:
 p=pathlib.Path(j['p']);f=p/('acro-riverview-'+str(j['n'])+'-authored.blend')
 with bpy.data.libraries.load(str(f),link=False) as (a,b): b.scenes=a.scenes
 assert len(b.scenes)==1
 s=b.scenes[0];s['supersedesAssetIds']=json.dumps(j['supersedes']);s['binding_status']='final root verified split binding'
 bpy.data.libraries.write(str(f),{s},fake_user=True,compress=True)
 bpy.data.batch_remove(ids=list(s.objects));bpy.data.scenes.remove(s)
 runpy.run_path(str(p/'check-standalone.py'),run_name='__main__')
 v=json.loads((p/'standalone-validation.json').read_text());assert json.loads(v['supersedesAssetIds'])==j['supersedes'];assert hashlib.sha256((p/('acro-riverview-'+str(j['n'])+'.glb')).read_bytes()).hexdigest()==j['sha'];results.append({'tower':j['n'],'supersedes':j['supersedes'],'glb_unchanged':True,'reload_pass':True})
assert before=={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes} and bpy.context.scene==old
out={'results':results,'initial_scene_restored':old.name,'scene_preserved':True}
pathlib.Path('/Users/hyemini/Documents/Codex/2026-09-21/seoul-real-estate-map/data/model-source/bespoke/acro-riverview-102-105-family/final-binding-proof.json').write_text(json.dumps(out,indent=2));print(json.dumps(out))
