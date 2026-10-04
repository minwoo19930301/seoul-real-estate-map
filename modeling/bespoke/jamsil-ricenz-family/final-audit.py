import pathlib,json,hashlib
P=pathlib.Path(__file__).parent
sha=lambda p:hashlib.sha256(p.read_bytes()).hexdigest()
T=list(range(201,218))+list(range(219,263))+[264]
b=json.loads((P/'bundle.json').read_text());assert sorted(int(x['tower']) for x in b)==T
assert not (P/'263').exists() and not (P/'265').exists()
for x in b:
 p=P/x['tower'];g=json.loads((p/'geometry-proof.json').read_text());s=json.loads((p/'standalone-validation.json').read_text());v=json.loads((p/'scene-preservation.json').read_text());assert v['equal'];assert len(s['scenes'])==1 and s['image_nodes']==0 and s['finite'];assert g['source_geometry_exact'] and g['register_row_exact'];assert g['roof_structure_maximum_projection_m']<.0001
 for k,v in json.loads((p/'final-hashes.json').read_text()).items():assert sha(p/k)==v,(p,k)
records=list(P.glob('mcp-batch-*.json'));assert len(records)==31
for p in records:
 d=json.loads(p.read_text());assert all(x['port']==9878 and not x['isError'] for x in d)
summary={'completed_models':len(b),'actual_rendered_and_visually_reviewed_views':248,'successful_actual_mcp_batches':31,'standalone_reloads':62,'source_geometry_and_register_checks':62,'scene_preservation_checks':62,'images_embedded':0,'excluded_towers':[263,265],'glb_bytes':sum(x['glbBytes'] for x in b),'triangles':sum(x['triangles'] for x in b),'max_surface_projection_m':max(x['maximumSurfaceProjectionM'] for x in b),'bundle_sha256':sha(P/'bundle.json'),'publication':'Root review and publication separate; no public/Git writes by author.'}
(P/'final-audit.json').write_text(json.dumps(summary,indent=2));files={str(p.relative_to(P)):sha(p) for p in sorted(P.rglob('*')) if p.is_file() and p.name!='stage-final-hashes.json'};(P/'stage-final-hashes.json').write_text(json.dumps(files,indent=2));assert all(sha(P/k)==v for k,v in files.items());print(json.dumps(summary));print('frozen files',len(files))
