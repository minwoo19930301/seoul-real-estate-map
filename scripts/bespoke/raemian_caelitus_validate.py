"""Validate the authored Caelitus assembly in its real Blender MCP session."""
import bpy,json,math
from pathlib import Path
from mathutils import Vector
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/raemian-caelitus'
D=json.loads((OUT/'authored-input.json').read_text());rows=[];by={101:[],102:[],103:[]}
for o in bpy.data.objects:
 if o.type!='MESH' or not o.get('caelitus_owner'):continue
 o.data.calc_loop_triangles();volume=0
 for v in o.data.vertices:assert all(math.isfinite(c) for c in v.co),(o.name,'nonfinite')
 for tri in o.data.loop_triangles:
  a,b,c=[o.data.vertices[i].co for i in tri.vertices];volume+=a.dot(b.cross(c))/6
 assert volume>0,(o.name,volume)
 row={'name':o.name,'owner':o['caelitus_owner'],'triangles':len(o.data.loop_triangles),'signedVolume':volume,'minZ':min((o.matrix_world@v.co).z for v in o.data.vertices),'maxZ':max((o.matrix_world@v.co).z for v in o.data.vertices)}
 rows.append(row);by[row['owner']].append(row)
for t in D['towers']:
 rr=by[t['number']];assert rr
 assert abs(min(r['minZ'] for r in rr))<1e-5,(t['number'],'ground',min(r['minZ'] for r in rr))
 assert abs(max(r['maxZ'] for r in rr)-t['crownTop'])<1e-4,(t['number'],'crown',max(r['maxZ'] for r in rr))
# A through-ray at the two booleans proves the canopy roof and wood soffit
# retain genuine openings after export geometry evaluation.
from mathutils import Matrix
T={t['number']:t for t in D['towers']};A=Matrix([[*T[n]['sitePlanCenter'],1] for n in [101,102,103]]);inv=A.inverted();ex=inv@Vector([T[n]['siteEN'][0] for n in [101,102,103]]);ey=inv@Vector([T[n]['siteEN'][1] for n in [101,102,103]])
voids=[]
for pixel in [(778,683),(860,651)]:
 p=Vector((*pixel,1));origin=Vector((ex.dot(p),ey.dot(p),10))
 for obj in [o for o in bpy.data.objects if o.type=='MESH' and 'with_two_oval_openings' in o.name]:
  assert not obj.ray_cast(obj.matrix_world.inverted()@origin,Vector((0,0,-1)),distance=10)[0],(obj.name,'oculus blocked',pixel)
 voids.append(pixel)
result={'blender':bpy.app.version_string,'finiteVertices':True,'positiveMeshVolumes':True,'groundMinZ':0,'towerCrownHeights':{t['number']:t['crownTop'] for t in D['towers']},'canopyThroughOpenings':voids,'sourceIds':[t['sourceId'] for t in D['towers']],'components':rows}
(OUT/'geometry-validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n')
print('CAELITUS_VALIDATED',len(rows),'components',sum(r['triangles'] for r in rows),'triangles')
