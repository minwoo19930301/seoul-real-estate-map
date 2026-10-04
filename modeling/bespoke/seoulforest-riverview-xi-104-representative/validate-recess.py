import pathlib,json,sys,numpy as np
P=pathlib.Path(__file__).parent;sys.path.insert(0,str(pathlib.Path.cwd()/'scripts/bespoke'));from validate_height_regions import read_triangles
D=json.loads((P/'source-data.json').read_text());tri=read_triangles(P/'seoulforest-riverview-xi-104.glb');r=D['ring_m'];a=np.array(r[9]);b=np.array(r[10]);n=np.array(D['central_recess']['outward_normal']);pitch=D['body_height_m']/D['floors'];results=[]
for t,bands in [(.415,[(3,7),(23,27)]),(.585,[(13,17),(33,37)])]:
 q=a+(b-a)*t+n*(-.6);hits=[]
 for tr in tri:
  xy=tr[:,[0,2]]*np.array([1,-1]);mat=np.stack([xy[1]-xy[0],xy[2]-xy[0]],axis=1);det=np.linalg.det(mat)
  if abs(det)<1e-9:continue
  u,v=np.linalg.solve(mat,q-xy[0])
  if u>=-1e-7 and v>=-1e-7 and u+v<=1+1e-7:hits.append(float(tr[0,1]+u*(tr[1,1]-tr[0,1])+v*(tr[2,1]-tr[0,1])))
 hits=sorted(set(round(z,4) for z in hits));expected=[0,1,112.55,113.05]+[f*pitch for band in bands for f in band];assert all(min(abs(z-x) for z in hits)<.001 for x in expected);assert not any(7*pitch+.01<z<13*pitch-.01 for z in hits)
 results.append({'station':t,'inward_depth_m':.6,'actual_vertical_ray_intersections_m':hits,'expected_supported_box_bands_floors':bands,'no_full_height_solid_occluding_recess':True})
(P/'recess-geometry-proof.json').write_text(json.dumps({'method':'Independent GLB triangles vertical-ray barycentric intersection through both box columns','results':results},indent=2));print(json.dumps(results))
