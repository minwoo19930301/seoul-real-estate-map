from pathlib import Path
import json,hashlib
B=Path('data/model-source/bespoke');O=B/'banpo-xi-115-129-family';P=B/'banpo-xi-130-144-family';P.mkdir(exist_ok=True)
s=(O/'prepare.py').read_text().replace('banpo-xi-115-129-family','banpo-xi-130-144-family').replace('range(115,130)','range(130,145)');(P/'prepare.py').write_text(s);exec(compile(s,str(P/'prepare.py'),'exec'))
bind=json.loads((B/'banpo-xi-fallback-review/published-model-binding-map.json').read_text());(P/'binding-map-frozen.json').write_text(json.dumps(bind,ensure_ascii=False,indent=2))
for t in range(130,145):
 p=P/str(t);d=json.loads((p/'source-data.json').read_text());b=next(x for x in bind['bindings'] if x['number']==t);assert b['sourceFootprintId']==d['id'];d['supersedesAssetIds']=b['supersedes'];d['binding_status']='published binding map exact source ID match';d['ancestor_glb_sha256']='b90310c2fe4f015abd1c58405b926afb9bad8e3cdf2dfbd645ea1d6cc280fd00';(p/'source-data.json').write_text(json.dumps(d,ensure_ascii=False,indent=2));(p/'build.py').write_text((O/'118/build.py').read_text().replace('BX118','BX'+str(t)))
for name in ['check-standalone.py','validate.py','finalize.py']:
 s=(O/name).read_text().replace('banpo-xi-115-129-family','banpo-xi-130-144-family').replace('range(115,130)','range(130,145)');(P/name).write_text(s)
for i,start in enumerate(range(130,145,3),1):
 (P/f'build-batch-{i}.py').write_text("import bpy,pathlib,json\nP=pathlib.Path(__file__).parent;old=bpy.context.scene;before={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes}\nfor t in map(str,range("+str(start)+","+str(start+3)+")):\n p=P/t/'build.py';exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})\nafter={s.name:sorted(o.name for o in s.objects) for s in bpy.data.scenes};assert before==after and bpy.context.scene==old\n(P/'scene-preservation-batch-"+str(i)+".json').write_text(json.dumps({'equal':before==after,'active_scene':old.name,'before':before,'after':after},indent=2))\n")
(P/'run-batches.py').write_text((O/'run-batches.py').read_text().replace('range(2,6)','range(1,6)'))
(P/'make-review-sheets.py').write_text((O/'make-review-sheets.py').read_text().replace('[115,120,125]','[130,135,140]'))
prior={}
for directory in ['banpo-xi-115-129-family','banpo-xi-105-114-family','banpo-xi-101-roof-contained','banpo-xi-101-102-104-register-corrected']:
 for p in (B/directory).rglob('*'):
  if p.is_file():prior[str(p)]=hashlib.sha256(p.read_bytes()).hexdigest()
(P/'prior-hashes.json').write_text(json.dumps(prior,indent=2));(P/'source-provenance.json').write_text(json.dumps({str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in [B/'banpo-xi-all44-research/modeling-ready-101-144.json',B/'banpo-xi-fallback-review/published-model-binding-map.json',B/'banpo-xi-101-roof-contained/banpo-xi-101.glb']},indent=2));print('prepared130–144, previous files',len(prior))
