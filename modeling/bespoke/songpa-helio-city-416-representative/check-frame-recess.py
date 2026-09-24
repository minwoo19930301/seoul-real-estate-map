import pathlib,json,sys,math,numpy as np
R=pathlib.Path.cwd();P=pathlib.Path(__file__).parent;sys.path.insert(0,str(R/'scripts/bespoke'));from validate_height_regions import read_triangles
D=json.loads((P/'source-data.json').read_text());tri=read_triangles(P/'songpa-helio-city-416.glb');tri=tri[:,:,[0,2,1]]*np.array([1,-1,1]);ta=tri[:,0];e1=tri[:,1]-ta;e2=tri[:,2]-ta

def ray(origin,direction):
 pv=np.cross(np.broadcast_to(direction,e2.shape),e2);det=np.einsum('ij,ij->i',e1,pv);good=np.abs(det)>1e-10;iv=np.zeros_like(det);iv[good]=1/det[good];tv=origin-ta;u=np.einsum('ij,ij->i',tv,pv)*iv;q=np.cross(tv,e1);v=np.einsum('j,ij->i',direction,q)*iv;t=np.einsum('ij,ij->i',e2,q)*iv;ok=good&(u>=-1e-7)&(v>=-1e-7)&(u+v<=1+1e-7)&(t>0);return float(t[ok].min())
r=D['ring_m'];area=sum(a[0]*b[1]-b[0]*a[1] for a,b in zip(r,r[1:]+r[:1]));pitch=D['body_height_m']/12;out=[]
for ei,(a,b) in enumerate(zip(r,r[1:]+r[:1])):
 L=math.dist(a,b)
 if L<16:continue
 tx,ty=(b[0]-a[0])/L,(b[1]-a[1])/L;nx,ny=(ty,-tx) if area>0 else(-ty,tx);direction=np.array([-nx,-ny,0]);count=max(4,round(L/3.7));bw=L/count
 for j,fs,fe in [(1,2,4),(count-2,8,10),(count//2+1,4,6)]:
  t=(j+.5)/count;cx=a[0]+(b[0]-a[0])*t;cy=a[1]+(b[1]-a[1])*t;z=(fs+.55)*pitch;inside=ray(np.array([cx+nx,cy+ny,z]),direction);w=bw*.96;front=ray(np.array([cx+tx*w/2+nx,cy+ty*w/2+ny,z]),direction);shelf=ray(np.array([cx+nx,cy+ny,fs*pitch+.15]),direction);assert 1.20<inside<1.39 and .64<front<.68 and .52<shelf<.56;out.append({'edge':ei,'bay':j,'two_source_floor_group':[fs,fe],'window_field_inward_depth_m':inside-1,'frame_outward_projection_m':1-front,'shelf_outward_projection_m':1-shelf,'actual_glb_rays':True})
(P/'frame-recess-proof.json').write_text(json.dumps({'frame_section_width_depth_m':[.34,.34],'dimensions_inferred':True,'source_storeys_preserved':12,'groups':out},indent=2));print(json.dumps(out))
