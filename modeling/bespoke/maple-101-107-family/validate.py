import bpy,bmesh,json,math
from pathlib import Path
from mathutils import Vector
O=Path(__file__).parent;NUMBER=int(bpy.data.filepath.split('maple-')[-1].split('.')[0]);D=json.loads((O/f'input-{NUMBER}.json').read_text());B=json.loads((O/f'build-summary-{NUMBER}.json').read_text());objs=[o for o in bpy.data.objects if o.type=='MESH'and o.get('asset_id')==D['id']];checks=[]
for o in objs:
 bm=bmesh.new();bm.from_mesh(o.data);checks.append({'name':o.name,'volume':bm.calc_volume(signed=True),'nonManifold':sum(not e.is_manifold for e in bm.edges),'finite':all(math.isfinite(c)for v in bm.verts for c in v.co),'identityTransform':all(abs(o.matrix_world[i][j]-(1 if i==j else 0))<1e-8 for i in range(4)for j in range(4))});bm.free()
assert len(objs)>100 and all(x['volume']>0 and x['nonManifold']==0 and x['finite']and x['identityTransform']for x in checks)
bounds={'min':[min(v.co[i]for o in objs for v in o.data.vertices)for i in range(3)],'max':[max(v.co[i]for o in objs for v in o.data.vertices)for i in range(3)]};assert abs(bounds['min'][2])<1e-6 and bounds['max'][2]<=D['heightM']+.001
V=[Vector(p)for p in D['ringEN']];rays=[]
for sample in B['windowSamples']:
 e=sample['e'];a,b=V[e],V[(e+1)%6];n=Vector((-(b-a).y,(b-a).x)).normalized();p=a+(b-a)*sample['t'];start=Vector((p.x+n.x*4,p.y+n.y*4,sample['z']));hit=bpy.context.scene.ray_cast(bpy.context.evaluated_depsgraph_get(),start,Vector((-n.x,-n.y,0)),distance=10)
 assert hit[0] and 'glass' in hit[4].active_material.name,(sample,str(hit));rays.append({**sample,'firstHit':hit[4].name,'material':hit[4].active_material.name})
# Old MCP scene orphan datablocks are not source assets. Remove unused datablocks and all images.
for im in list(bpy.data.images):bpy.data.images.remove(im)
for db in [bpy.data.meshes,bpy.data.materials,bpy.data.curves]:
 for item in list(db):
  if item.users==0:db.remove(item)
assert len(bpy.data.images)==0
(O/f'geometry-validation-{NUMBER}.json').write_text(json.dumps({'status':'PASS','boundsBlenderENU':bounds,'components':checks,'windowRays':rays,'roofFootprintSupportChecks':len(B['roofSupport']),'unitScale':bpy.context.scene.unit_settings.scale_length,'exclusiveOwnership':all(o.get('asset_id')==D['id'] for o in bpy.data.objects if o.type=='MESH'),'noImagesInBlend':True,'scope':'Geometry and window visibility checks; representative family inference, not individual all-face photo validation.'},indent=2));bpy.ops.wm.save_as_mainfile(filepath=str(O/f'maple-{NUMBER}.blend'));print('VALIDATION_PASS',NUMBER,len(checks),len(rays),bounds)
