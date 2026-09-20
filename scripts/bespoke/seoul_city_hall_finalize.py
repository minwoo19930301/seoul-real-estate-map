"""Validate the staged City Hall exports and bind the completed real MCP record.
Run after seoul_city_hall.py has returned through the MCP client. Does not publish.
"""
import hashlib,json,math,struct
from pathlib import Path
ROOT=Path(__file__).resolve().parents[2]
OUT=ROOT/'data/model-source/bespoke/seoul-city-hall'
bundle=json.loads((OUT/'bundle.json').read_text());proof=OUT/'mcp-build.json'
assert proof.is_file()
proof_json=json.loads(proof.read_text())
assert 'Successfully executed code' in json.dumps(proof_json) or 'Code executed successfully' in json.dumps(proof_json), 'MCP execution must have succeeded'
validation=[]
for asset in bundle['assets']:
 path=Path(asset['file']);raw=path.read_bytes();length=struct.unpack_from('<I',raw,12)[0];gltf=json.loads(raw[20:20+length]);blob=raw[28+length:]
 def vectors(index):
  a=gltf['accessors'][index];view=gltf['bufferViews'][a['bufferView']];assert a['componentType']==5126 and a['type']=='VEC3';start=view.get('byteOffset',0)+a.get('byteOffset',0);stride=view.get('byteStride',12)
  return [struct.unpack_from('<fff',blob,start+i*stride) for i in range(a['count'])]
 points=[];normals=[];triangles=0
 for mesh in gltf['meshes']:
  for primitive in mesh['primitives']:
   points.extend(vectors(primitive['attributes']['POSITION']));normals.extend(vectors(primitive['attributes']['NORMAL']));triangles+=gltf['accessors'][primitive['indices']]['count']//3
 assert all(math.isfinite(v) for p in points+normals for v in p)
 error=max(abs(math.sqrt(sum(v*v for v in p))-1) for p in normals);assert error<1e-4
 low=[min(p[k] for p in points) for k in range(3)];high=[max(p[k] for p in points) for k in range(3)];assert abs(low[1])<1e-6
 assert not gltf.get('images'), 'No source photographs or textures embedded'
 asset.update(sha256=hashlib.sha256(raw).hexdigest(),triangles=triangles,meshCount=len(gltf['meshes']),materialCount=len(gltf['materials']),heightM=high[1],bounds={'min':low,'max':high})
 asset['heightBasis']='New shell nominal 47.4m author estimate; roof louvers yield 48.22m total; no official metric height verified.' if asset['id'].endswith('-new') else 'OSM source-reported unverified component heights, including 35m finial.'
 asset['floors']=13 if asset['id'].endswith('-new') else 4
 asset['floorsBasis']='Official Seoul construction/floor guide; roof terrace is not an extra full historic storey.'
 validation.append({'id':asset['id'],'bytes':len(raw),'sha256':asset['sha256'],'triangles':triangles,'meshes':len(gltf['meshes']),'materials':len(gltf['materials']),'bounds':asset['bounds'],'maxUnitNormalError':error,'embeddedImages':0})
owned=[i for a in bundle['assets'] for i in a['footprintIds']];assert len(owned)==9 and len(set(owned))==9
bundle['mcpEvidence']=[{'path':'docs/model-audit/mcp/seoul-city-hall/build.json','sha256':hashlib.sha256(proof.read_bytes()).hexdigest(),'tool':'execute_blender_code','port':9876,'stageFile':str(proof)}]
bundle['sourceCodeSha256']=hashlib.sha256((ROOT/'scripts/bespoke/seoul_city_hall.py').read_bytes()).hexdigest()
(OUT/'geometry-validation.json').write_text(json.dumps(validation,indent=2));(OUT/'bundle.json').write_text(json.dumps(bundle,ensure_ascii=False,indent=2))
recipe=json.loads((OUT/'architecture-recipe.json').read_text());recipe['assets']=bundle['assets'];recipe['newHeightBasis']=bundle['assets'][0]['heightBasis'];recipe['reviewRevisions']=['Replaced continuous white upper bar with western auditorium and eastern terraces from the upper-floor plan.','Replaced radial lens fan with clipped glass/metal facet grid.','Separated lighter surface mullions from darker alternating/crossed inner structural braces.','Connected historic clock part to its 18m supporting body; the 22m adjacent source part has a tower-shaped notch.','Added stepped clock base and tiered finial; warm stone palette and explicit 9-ID split ownership.'];(OUT/'architecture-recipe.json').write_text(json.dumps(recipe,ensure_ascii=False,indent=2))
print(json.dumps({'assets':validation,'mcpEvidence':bundle['mcpEvidence']},indent=2))
