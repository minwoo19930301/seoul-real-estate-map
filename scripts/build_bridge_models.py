"""Bridge reconstruction from retrieved OSM deck outlines. Piers/detail positions are estimates."""
from pathlib import Path
import json,hashlib,math
import numpy as np
from shapely.geometry import shape,Polygon,LineString,Point
from shapely.ops import transform
from build_district_landmarks import Mesh,projected,unprojected,oriented_frame,raw_asset_records
ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'public/models'

def beam(mesh,a,b,width,color,mat=2):
 a=np.array(a,float);b=np.array(b,float);direction=b-a;length=np.linalg.norm(direction)
 if length<.001:return
 direction/=length;axis=np.array([0,1,0]) if abs(direction[1])<.9 else np.array([1,0,0]);u=np.cross(direction,axis);u=u/np.linalg.norm(u)*width/2;v=np.cross(direction,u)
 q=[a-u-v,a+u-v,a+u+v,a-u+v,b-u-v,b+u-v,b+u+v,b-u+v]
 for i,j,k,l in [(0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)]:mesh.quad(mat,q[i],q[j],q[k],q[l],color)

def build():
 source=json.loads((ROOT/'public/bridge-outlines.geojson').read_text());manifestfile=OUT/'manifest.json';oldtext=manifestfile.read_text();old=json.loads(oldtext);raw=raw_asset_records(oldtext);new=[];evidence=[]
 matches=json.loads((OUT/'footprint-matches.json').read_text());oldmatches=json.loads(json.dumps(matches))
 for f in source['features']:
  p=f['properties'];name=p['nameKo'];identifier='bridge-'+p['sourceId'].replace('osm:','').replace('/','-');path=OUT/(identifier+'.glb');assert not path.exists(),identifier
  geo=shape(f['geometry']).buffer(0);anchor=(geo.centroid.x,geo.centroid.y);local=transform(lambda x,y,z=None:projected(x,y,anchor),geo);polys=[local] if local.geom_type=='Polygon' else list(local.geoms)
  mesh=Mesh();deck=24 if name=='반포대교' else 5 if name=='잠수교' else 18;steel=[.55,.62,.64];concrete=[.69,.70,.66];road=[.19,.22,.24]
  arches=name in ('한강대교','동작대교','서강대교','당산철교');truss=name in ('성수대교','성산대교','동호대교','한강철교');cable=name in ('올림픽대교','월드컵대교')
  for poly in polys:
   if poly.area<5:continue
   mesh.solid(poly,deck-2,deck,concrete,road)
   # Deck edge rails follow the actual outline, including bends.
   coords=list(poly.exterior.coords)
   for a,b in zip(coords,coords[1:]):
    beam(mesh,(a[0],deck+.7,a[1]),(b[0],deck+.7,b[1]),.24,steel)
   cx,cz,ux,uz,length,width=oriented_frame(poly)
   def pos(t,y,v=0):return(cx+ux*t-uz*v,y,cz+uz*t+ux*v)
   # Source polygon intersections keep estimated piers under the actual deck.
   for t in np.arange(-length/2+25,length/2-15,65):
    cross=LineString([(pos(t,0,-width)[0],pos(t,0,-width)[2]),(pos(t,0,width)[0],pos(t,0,width)[2])]);section=poly.intersection(cross)
    for line in [section] if section.geom_type=='LineString' else getattr(section,'geoms',[]):
     if line.geom_type!='LineString' or line.length<2:continue
     mid=line.interpolate(.5,normalized=True);beam(mesh,(mid.x,0,mid.y),(mid.x,deck-2,mid.y),2.3,concrete,0)
   # Road/rail deck markings are illustrative and clipped to the real footprint.
   for t in np.arange(-length/2+10,length/2-10,18):
    a=pos(t,deck+.035);b=pos(t+7,deck+.035)
    if poly.covers(LineString([(a[0],a[2]),(b[0],b[2])])):beam(mesh,a,b,.14,[.92,.87,.62],1)
   if (arches or truss) and length>180:
    span=100 if name!='서강대교' else 200
    for start in np.arange(-length/2+25,length/2-span,span):
     for side in [-1,1]:
      lateral=side*min(12,width*.32)
      # Only structural cues whose frame stays over this deck component.
      if not poly.covers(Point(pos(start+span/2,0,lateral)[0],pos(start+span/2,0,lateral)[2])):continue
      base=deck+1 if arches else deck-1
      rise=18 if arches else -7
      for i in range(12):
       t0=start+span*i/12;t1=start+span*(i+1)/12
       y0=base+rise*math.sin(math.pi*i/12);y1=base+rise*math.sin(math.pi*(i+1)/12)
       beam(mesh,pos(t0,y0,lateral),pos(t1,y1,lateral),.7,steel)
       beam(mesh,pos(t0,base,lateral),pos(t0,y0,lateral),.38,steel)
       if truss:beam(mesh,pos(t0,y0,lateral),pos(t1,base,lateral),.4,steel)
  # Signature cable-stayed pylon cues, with published nominal height but estimated datum/placement.
  if cable:
   poly=max(polys,key=lambda x:x.area);cx,cz,ux,uz,length,width=oriented_frame(poly);t=-length*.06 if name=='월드컵대교' else 0;top=100 if name=='월드컵대교' else 88
   def pos(s,y,v=0):return(cx+ux*s-uz*v,y,cz+uz*s+ux*v)
   lean=20 if name=='월드컵대교' else 0
   for u,v in ([(-7,-7),(-7,7),(7,-7),(7,7)] if name=='올림픽대교' else [(-3,-5),(3,5)]):beam(mesh,pos(t+u,deck,v),pos(t+lean,top,0),2.1,concrete)
   for sign in [-1,1]:
    for i in range(1,13):beam(mesh,pos(t+lean,top-3),pos(t+sign*(35+i*15),deck+.3),.22,[.76,.76,.69])
   if name=='올림픽대교':beam(mesh,pos(t,top),pos(t,top+7),3,[.55,.40,.23])
  stats,offset=mesh.save(path);lon,lat=unprojected(offset[0],offset[2],anchor)
  asset={'id':identifier,'model':path.name,'name':name,'nameKo':name,'category':'bridge','minZoom':12.5,'units':'metres',**stats,'rootTransform':'identity','coordinate':{'lon':lon,'lat':lat,'basis':'bounds centre of source bridge outline model'},'geoBounds':list(geo.bounds),'yawDegFromEast':0,'heightDatum':'Estimated deck clearance above local river terrain; structure cues reconstructed, not surveyed.','referenceUrl':p['sourceUrl'],'sources':[{'url':p['sourceUrl'],'supports':['bridge plan geometry and identity']}],'heightEstimated':True,'footprintIds':[],'roadGeometrySource':p['geometrySource'],'modelingEstimates':{'deckClearanceM':deck,'piers':'regular spacing under source deck; actual pier locations not surveyed','railingsAndMarkings':'illustrative','signatureStructure':'cable-stayed' if cable else 'arch' if arches else 'truss' if truss else 'girder','pylonDatum':'Published nominal 88m/100m represented against local model floor; exact vertical survey datum not available' if cable else None},'validation':{'noExternalResources':True}}
  if cable:asset['sources'].append({'url':'https://culture.seoul.go.kr/night/sub/viewSpot/view.do?viewId=69' if name=='올림픽대교' else 'https://kids.seoul.go.kr/article/articleView.do?p_articleSn=801474','supports':['nominal pylon height and structural form']})
  new.append(asset);matches[identifier]=[];evidence.append({'id':identifier,'nameKo':name,'source':p,'modelingEstimates':asset['modelingEstimates']})
  print(name,stats['triangles'],'triangles',flush=True)
 old['assets']+=new;old['infrastructureExpansion']={'bridgeCount':len(new),'source':'/bridge-outlines.geojson','provenance':'../../docs/BRIDGE_MODEL_PROVENANCE.json'}
 # Serialize old asset record text verbatim; append new records only.
 meta={k:v for k,v in old.items() if k!='assets'};prefix=json.dumps(meta,ensure_ascii=False,indent=2)[:-2]+',\n  "assets": [\n'
 records=['    '+v for v in raw.values()]+['\n'.join('    '+line for line in json.dumps(a,ensure_ascii=False,indent=2).splitlines()) for a in new]
 manifestfile.write_text(prefix+',\n'.join(records)+'\n  ]\n}\n');(OUT/'footprint-matches.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2)+'\n')
 assert all(raw[k]==raw_asset_records(manifestfile.read_text())[k] for k in raw)
 assert all(matches[k]==v for k,v in oldmatches.items())
 (ROOT/'docs/BRIDGE_MODEL_PROVENANCE.json').write_text(json.dumps({'bridges':evidence,'scope':'Actual OSM plan outlines or explicitly buffered source centerlines. Deck clearance, structural-member proportions and supports are estimates.'},ensure_ascii=False,indent=2)+'\n')
 print('Bridge models',len(new))
if __name__=='__main__':build()
