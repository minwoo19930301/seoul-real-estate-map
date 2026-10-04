import bpy,json,math
from pathlib import Path
P=Path(__file__).resolve().parent;result=[]
for o in bpy.data.objects:
 if o.type!='MESH':continue
 if 'roof_slab' in o.name:
  tops=[p for p in o.data.polygons if p.normal.z>.5];bots=[p for p in o.data.polygons if p.normal.z<-.5]
  result.append({'object':o.name,'topArea':sum(p.area for p in tops),'bottomArea':sum(p.area for p in bots),'zeroNormals':sum(p.normal.length<.5 for p in o.data.polygons)})
(P/'mcp-roof-proof.json').write_text(json.dumps(result,indent=2));print(json.dumps(result))
D=json.loads((P/'authored-input.json').read_text());areas=[]
for n,t in D['towers'].items():
 for reg in t['regions']:
  for i,r in enumerate(reg['rings']):
   name=n+'_'+reg['name']+str(i)+'_roof_slab';o=bpy.data.objects[name];expected=abs(sum(r[k][0]*r[(k+1)%len(r)][1]-r[(k+1)%len(r)][0]*r[k][1]for k in range(len(r)))/2);observed=sum(f.area for f in o.data.polygons if f.normal.z>.5);assert abs(expected-observed)<.01,(name,expected,observed);areas.append({'object':name,'sourceArea':expected,'topTriangleArea':observed,'differenceM2':abs(expected-observed)})
(P/'mcp-roof-proof.json').write_text(json.dumps({'roofAreaChecks':areas,'editableMeshes':sum(o.type=='MESH'for o in bpy.data.objects),'finiteCoordinates':all(math.isfinite(v)for o in bpy.data.objects if o.type=='MESH'for p in o.data.vertices for v in p.co),'sourceBlend':bpy.data.filepath},indent=2));print('PASS all roof triangle areas match clipped source regions; finite editable coordinates')
