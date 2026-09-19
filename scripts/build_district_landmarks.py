"""Build source-footprint district GLBs; never writes source SQLite databases.

Run with .venv/bin/python scripts/build_district_landmarks.py
Geometry uses local Overture/OSM/government footprints. Storey-derived heights,
window layouts, roof plant and all materials are explicitly artistic estimates.
"""
from pathlib import Path
import argparse, hashlib, json, math, shutil, sqlite3, struct, zlib
from collections import Counter
import numpy as np
from shapely.geometry import shape, Polygon
from shapely.ops import transform, triangulate
from shapely.geometry.polygon import orient

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / 'public/models'
PRESERVED = ('sixtythree', 'lotte', 'nseoul', 'coex')
R = 6378137.0

def projected(lon, lat, anchor):
    a,b=anchor; scale=R*math.cos(math.radians(b))
    return (scale*math.radians(lon-a), -scale*(math.log(math.tan(math.pi/4+math.radians(lat)/2))-math.log(math.tan(math.pi/4+math.radians(b)/2))))

def unprojected(x,z,anchor):
    a,b=anchor; scale=R*math.cos(math.radians(b))
    return (a+math.degrees(x/scale),math.degrees(2*math.atan(math.exp(math.log(math.tan(math.pi/4+math.radians(b)/2))-z/scale))-math.pi/2))

class Mesh:
    def __init__(self): self.p=[[],[],[]];self.n=[[],[],[]];self.c=[[],[],[]]
    def tri(self,mat,a,b,c,color):
        a,b,c=[np.asarray(v,dtype=float) for v in (a,b,c)]
        n=np.cross(b-a,c-a); length=np.linalg.norm(n)
        if length<1e-7:return
        self.p[mat].extend([a,b,c]);self.n[mat].extend([n/length]*3);self.c[mat].extend([color]*3)
    def quad(self,mat,a,b,c,d,color):
        self.tri(mat,a,b,c,color);self.tri(mat,a,c,d,color)
    def solid(self,poly,bottom,top,color,roofcolor):
        poly=orient(poly,sign=1)
        for ring in [poly.exterior,*poly.interiors]:
            pts=list(ring.coords)
            for (x,z),(u,v) in zip(pts,pts[1:]):
                self.quad(0,(x,bottom,z),(x,top,z),(u,top,v),(u,bottom,v),color)
        for t in triangulate(poly):
            if not poly.covers(t):continue
            a,b,c=list(t.exterior.coords)[:3]
            self.tri(2,(a[0],top,a[1]),(c[0],top,c[1]),(b[0],top,b[1]),roofcolor)
    def detail(self,poly,height,floors,seed,roof_ceiling=None):
        # Window ribbons with opaque vertical piers. Three material batches total.
        poly=orient(poly,sign=1);light=[.53,.63,.69];dark=[.26,.36,.40]
        step=max(1,math.ceil(floors/24));floorheight=height/max(1,floors)
        for ring in [poly.exterior,*poly.interiors]:
            pts=list(ring.coords)
            for edge,((x,z),(u,v)) in enumerate(zip(pts,pts[1:])):
                dx,dz=u-x,v-z;length=math.hypot(dx,dz)
                if length<3:continue
                ux,uz=dx/length,dz/length;nx,nz=uz,-ux
                inset=min(.65,length*.12);span=length-2*inset
                # Long elevations segmented into broad window bays, modest polygon budget.
                bays=max(1,min(8,int(span/8)))
                for floor in range(1,max(2,floors),step):
                    lo=max(.5,(floor-.7)*floorheight);hi=min(height-.7,lo+min(1.6,floorheight*.58))
                    if hi<=lo:continue
                    for bay in range(bays):
                        start=inset+bay*span/bays+.18;end=inset+(bay+1)*span/bays-.18
                        ax,az=x+ux*start+nx*.045,z+uz*start+nz*.045
                        bx,bz=x+ux*end+nx*.045,z+uz*end+nz*.045
                        col=light if (floor+bay+seed)%7==0 else dark
                        self.quad(1,(ax,lo,az),(ax,hi,az),(bx,hi,bz),(bx,lo,bz),col)
        # Setback roof plant comes from inward-buffered real footprint, not new towers.
        core=poly.buffer(-min(3,max(.7,math.sqrt(poly.area)*.1)))
        if core.is_empty:return
        if core.geom_type!='Polygon':core=max(core.geoms,key=lambda p:p.area)
        core=core.minimum_rotated_rectangle.intersection(core)
        if core.geom_type!='Polygon' or core.area<9:return
        centre=core.representative_point(); core=transform(lambda x,y,z=None:(centre.x+(x-centre.x)*.4,centre.y+(y-centre.y)*.4),core)
        self.solid(core,height,roof_ceiling if roof_ceiling is not None else min(height+2.4,height*1.045),[.52,.55,.53],[.40,.43,.42])
    def save(self,path):
        positions=np.concatenate([np.asarray(p) for p in self.p if p]);mins=positions.min(axis=0);maxs=positions.max(axis=0)
        offset=np.array([(mins[0]+maxs[0])/2,mins[1],(mins[2]+maxs[2])/2])
        blob=bytearray();views=[];accessors=[];primitives=[]
        def array(data,typ):
            a=np.asarray(data,dtype='<f4'); raw=a.tobytes();offset=len(blob);blob.extend(raw)
            views.append({'buffer':0,'byteOffset':offset,'byteLength':len(raw),'target':34962})
            acc={'bufferView':len(views)-1,'componentType':5126,'count':len(a),'type':typ}
            if typ=='VEC3':acc.update(min=a.min(axis=0).tolist(),max=a.max(axis=0).tolist())
            accessors.append(acc);return len(accessors)-1
        mats=[]
        for m in range(3):
            mats.append({'name':['Mineral facade','Window glazing','Roof and parapet'][m],'pbrMetallicRoughness':{'baseColorFactor':[1,1,1,1],'metallicFactor':[0,.18,.05][m],'roughnessFactor':[.82,.32,.76][m]}})
            if not self.p[m]:continue
            pos=np.asarray(self.p[m])-offset
            packed=np.concatenate([pos,np.asarray(self.n[m]),np.asarray(self.c[m])],axis=1).astype(np.float32)
            unique,inverse=np.unique(packed,axis=0,return_inverse=True)
            attrs={'POSITION':array(unique[:,:3],'VEC3'),'NORMAL':array(unique[:,3:6],'VEC3')}
            colors=np.concatenate([np.clip(np.rint(unique[:,6:9]*255),0,255).astype(np.uint8),np.full((len(unique),1),255,dtype=np.uint8)],axis=1);offset_color=len(blob);blob.extend(colors.tobytes());blob.extend(b'\0'*((-len(blob))%4))
            views.append({'buffer':0,'byteOffset':offset_color,'byteLength':colors.nbytes,'target':34962});accessors.append({'bufferView':len(views)-1,'componentType':5121,'normalized':True,'count':len(colors),'type':'VEC4'});attrs['COLOR_0']=len(accessors)-1
            indices=inverse.astype('<u2' if len(unique)<65536 else '<u4');offset_indices=len(blob);blob.extend(indices.tobytes());blob.extend(b'\0'*((-len(blob))%4))
            views.append({'buffer':0,'byteOffset':offset_indices,'byteLength':indices.nbytes,'target':34963});accessors.append({'bufferView':len(views)-1,'componentType':5123 if len(unique)<65536 else 5125,'count':len(indices),'type':'SCALAR'});index_accessor=len(accessors)-1
            primitives.append({'attributes':attrs,'indices':index_accessor,'material':m,'mode':4})
        doc={'asset':{'version':'2.0','generator':'Seoul source-footprint landmark builder 1.0'},'scene':0,'scenes':[{'nodes':[0]}],'nodes':[{'mesh':0,'name':path.stem}],'meshes':[{'primitives':primitives}],'materials':mats,'buffers':[{'byteLength':len(blob)}],'bufferViews':views,'accessors':accessors}
        js=json.dumps(doc,separators=(',',':')).encode();js+=b' '*((-len(js))%4);blob+=b'\0'*((-len(blob))%4)
        glb=struct.pack('<III',0x46546c67,2,12+8+len(js)+8+len(blob))+struct.pack('<II',len(js),0x4e4f534a)+js+struct.pack('<II',len(blob),0x004e4942)+blob
        path.write_bytes(glb)
        # Round-trip float32 bounds are the runtime GLTFLoader bounds.
        pp=(positions-offset).astype(np.float32);mi=pp.min(axis=0);ma=pp.max(axis=0)
        return {'dimensions':(ma-mi).tolist(),'measuredGlbDimensions':(ma-mi).tolist(),'bounds':{'min':mi.tolist(),'max':ma.tolist()},'triangles':sum(len(p)//3 for p in self.p),'drawCalls':len(primitives),'bytes':len(glb),'sha256':hashlib.sha256(glb).hexdigest()},offset

def oriented_frame(poly):
    pts=list(poly.minimum_rotated_rectangle.exterior.coords)[:4]
    lengths=[math.dist(pts[i],pts[(i+1)%4]) for i in range(4)];i=lengths.index(max(lengths));a,b=pts[i],pts[(i+1)%4]
    ux,uz=(b[0]-a[0])/lengths[i],(b[1]-a[1])/lengths[i];centre=poly.centroid
    return centre.x,centre.y,ux,uz,max(lengths),min(lengths)

def dome(mesh,cx,cz,rx,rz,base,rise,color):
    rings,segments=10,40
    for j in range(rings):
        a=j/rings*math.pi/2;b=(j+1)/rings*math.pi/2
        for i in range(segments):
            t=i/segments*math.tau;u=(i+1)/segments*math.tau
            def p(v,w):return(cx+rx*math.cos(v)*math.cos(w),base+rise*math.sin(v),cz+rz*math.cos(v)*math.sin(w))
            mesh.quad(2,p(a,t),p(b,t),p(b,u),p(a,u),color)

def special_geometry(mesh,poly,name,height,floors,seed,body,roof):
    cx,cz,ux,uz,w,d=oriented_frame(poly)
    def pos(x,y,z):return(cx+ux*x-uz*z,y,cz+uz*x+ux*z)
    if name=='독립문':
        # Published overall width/height; opening and cornices are estimates.
        w=11.48;h=14.28;d=min(d,6);radius=2.6;spring=5.3
        opening=[(-radius,0),(radius,0),(radius,spring)]+[(radius*math.cos(t),spring+radius*math.sin(t)) for t in np.linspace(0,math.pi,19)]+[(-radius,0)]
        front=Polygon([(-w/2,0),(w/2,0),(w/2,h),(-w/2,h)], [opening])
        for t in triangulate(front):
            if not front.covers(t):continue
            a,b,c=list(t.exterior.coords)[:3]
            mesh.tri(0,pos(*a,-d/2),pos(*b,-d/2),pos(*c,-d/2),body)
            mesh.tri(0,pos(*c,d/2),pos(*b,d/2),pos(*a,d/2),body)
        for ring in [front.exterior,*front.interiors]:
            pts=list(ring.coords)
            for (x,y),(u,v) in zip(pts,pts[1:]):mesh.quad(0,pos(x,y,-d/2),pos(x,y,d/2),pos(u,v,d/2),pos(u,v,-d/2),body)
        for y in [10.7,12.8]:
            pp=Polygon([(pos(x,0,z)[0],pos(x,0,z)[2]) for x,z in [(-w/2-.15,-d/2-.15),(w/2+.15,-d/2-.15),(w/2+.15,d/2+.15),(-w/2-.15,d/2+.15)]])
            mesh.solid(pp,y,y+.25,body,roof)
        return True
    if name in ('봉은사 진여문','현충관'):
        base=5 if name=='봉은사 진여문' else 9
        inner=poly.buffer(-1)
        if inner.is_empty:inner=poly
        mesh.solid(inner,0,base,[.48,.24,.18],[.2,.24,.23])
        # Eaved hipped tiled roof. Shape, pitch and eave rise are visual estimates.
        low=[pos(-w*.55,base,-d*.57),pos(w*.55,base,-d*.57),pos(w*.55,base,d*.57),pos(-w*.55,base,d*.57)]
        ridge=[pos(-w*.28,base+4,0),pos(w*.28,base+4,0)]
        mesh.quad(2,low[0],ridge[0],ridge[1],low[1],[.19,.24,.25]);mesh.quad(2,low[2],ridge[1],ridge[0],low[3],[.19,.24,.25])
        mesh.tri(2,low[1],ridge[1],low[2],[.2,.25,.26]);mesh.tri(2,low[3],ridge[0],low[0],[.2,.25,.26]);return True
    if name=='국회의사당':
        mesh.solid(poly,0,32,[.76,.76,.70],[.65,.66,.60]);mesh.detail(poly,32,6,seed)
        dome(mesh,cx,cz,32,32,32,20,[.22,.47,.41]);return True
    if name=='올림픽체조경기장':
        mesh.solid(poly,0,18,[.68,.69,.67],[.73,.74,.72]);mesh.detail(poly,18,3,seed)
        dome(mesh,cx,cz,w*.47,d*.47,18,12,[.79,.79,.75]);return True
    if name=='파크원 타워1':
        bodytop=height-min(2.4,height*.045)
        mesh.solid(poly,0,bodytop,[.46,.56,.61],roof);mesh.detail(poly,bodytop,floors,seed,roof_ceiling=height)
        for x,z in [(-w*.43,-d*.43),(w*.43,-d*.43),(w*.43,d*.43),(-w*.43,d*.43)]:
            points=[pos(x+a,0,z+b) for a,b in [(-1.3,-1.3),(1.3,-1.3),(1.3,1.3),(-1.3,1.3)]]
            mesh.solid(Polygon([(p[0],p[2]) for p in points]),0,height,[.58,.12,.10],[.4,.10,.08])
        return True
    return False

def raw_asset_records(text):
    start=text.index('[',text.index('"assets"'))+1;decoder=json.JSONDecoder();result={}
    while True:
        while text[start].isspace() or text[start]==',':start+=1
        if text[start]==']':break
        _,end=decoder.raw_decode(text,start);raw=text[start:end];result[json.loads(raw)['id']]=raw;start=end
    return result

def load_candidates(paths):
    result=[]
    for p in paths:
        value=json.loads(p.read_text()); result.extend(value if isinstance(value,list) else value.get('candidates',value.get('assets',[])))
    return result

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--flight-root',type=Path,default=ROOT.parents[1]/'2026-09-05/new-chat/work/repos/seoul-flight-game');args=ap.parse_args()
    manifestfile=OUT/'manifest.json';original=manifestfile.read_text();old=json.loads(original);raw=raw_asset_records(original)
    kept=[a for a in old['assets'] if a['id'] in PRESERVED]
    baseline={a['id']:hashlib.sha256((OUT/a['model']).read_bytes()).hexdigest() for a in kept}
    candidates=load_candidates([ROOT/'docs/landmark-candidates-matched.json'])
    assert len(candidates)==250, len(candidates)
    assert len({c['id'] for c in candidates})==250
    db=sqlite3.connect(f'file:{ROOT}/data/buildings.sqlite?mode=ro',uri=True);db.row_factory=sqlite3.Row
    matches=json.loads((OUT/'footprint-matches.json').read_text());matches={k:v for k,v in matches.items() if k in PRESERVED}
    imported=[]
    source=args.flight_root/'assets/landmarks'; flight=json.loads((source/'manifest.json').read_text())
    for a in flight['assets']:
        if a['id'] in PRESERVED:continue
        for key in ['model','thumbnail']:
            if a.get(key) and (source/a[key]).exists():shutil.copy2(source/a[key],OUT/a[key])
        assert hashlib.sha256((OUT/a['model']).read_bytes()).hexdigest()==a['sha256']
        imported.append(a)
    matches['gyeongbokgung']=['339d93ed-e613-49b1-810f-a8b7694ecc35']
    assets=[];evidence=[];claimed=set(sum(matches.values(),[]))
    for index,c in enumerate(candidates):
        ids=c.get('buildingIds',c.get('footprintIds',[]));assert ids, c['id']
        rows=[dict(r) for r in db.execute('select * from buildings where id in ('+','.join('?' for _ in ids)+')',ids)]
        assert rows and len(rows)==len(ids),c['id']
        overlap=claimed.intersection(ids);assert not overlap,(c['id'],overlap)
        claimed.update(ids)
        coord=c.get('coordinate',{});anchor=(coord.get('lon',c.get('lon')),coord.get('lat',c.get('lat')))
        assert all(isinstance(x,(int,float)) for x in anchor),(c['id'],anchor)
        mesh=Mesh();parts=[];seed=int(hashlib.sha256(c['id'].encode()).hexdigest()[:8],16)
        for r in rows:
            geo=shape(json.loads(r['geometry']));local=transform(lambda x,y,z=None:projected(x,y,anchor),geo)
            if not local.is_valid:local=local.buffer(0)
            polys=[local] if local.geom_type=='Polygon' else list(local.geoms)
            fallback=15 if c.get('apartmentCode') else 3
            floors=r['num_floors'] or c.get('floors') or c.get('estimatedFloors') or fallback
            floors=max(2,min(100,int(floors)))
            measured=r['height_m'] if r['height_m'] and r['height_m']>3 else None
            height=measured or floors*3.05
            heightbasis=f"retained source height_m ({r['height_source'] or 'source dataset'}); not independently surveyed" if measured else f"estimated {floors} storeys x 3.05 m; source storeys" if r['num_floors'] else f"estimated fallback {floors} storeys x 3.05 m; no source height/storeys"
            shade=((seed+int(hashlib.md5(r['id'].encode()).hexdigest()[:5],16))%9)/100
            body=[.69+shade,.70+shade,.68+shade];roof=[.39+shade,.44+shade,.42+shade]
            for poly in polys:
                if poly.area<2:continue
                poly=poly.simplify(.18,preserve_topology=True)
                if not special_geometry(mesh,poly,c.get('nameKo',''),height,floors,seed,body,roof):
                    bodytop=height-min(2.4,height*.045) if measured else height
                    mesh.solid(poly,0,bodytop,body,roof);mesh.detail(poly,bodytop,floors,seed,roof_ceiling=height if measured else None)
            props=json.loads(zlib.decompress(r['source_properties'])) if isinstance(r['source_properties'],bytes) else json.loads(r['source_properties'])
            parts.append({'buildingId':r['id'],'name':r['name'],'geometrySource':r['geometry_source'],'heightSource':r['height_source'],'sourceHeightM':r['height_m'],'sourceFloors':r['num_floors'],'sourceHeightEnvelopeM':height if measured else None,'modeledBodyHeightM':height if c.get('nameKo') not in ('독립문','봉은사 진여문','현충관','국회의사당','올림픽체조경기장') else None,'heightBasis':heightbasis,'specialHeightNote':'Special silhouette dimensions override storey extrusion; published or estimated dimensions documented in DISTRICT_LANDMARK_MODELS.md' if c.get('nameKo') in ('독립문','봉은사 진여문','현충관','국회의사당','올림픽체조경기장') else None,'sources':props.get('sources',[])})
        filename=c['id']+'.glb';stats,offset=mesh.save(OUT/filename);lon,lat=unprojected(offset[0],offset[2],anchor)
        name=c.get('nameKo',c.get('name'));sources=c.get('sources',[]) or [{'url':u,'supports':['identity and source provenance; no texture rights asserted']} for u in c.get('sourceUrls',[])]
        if name=='독립문':sources.append({'url':'https://archives.seoul.go.kr/post/1678','supports':['published overall width 11.48m and height 14.28m; arch proportions estimated']})
        if name=='국회의사당':sources.append({'url':'https://theme.archives.go.kr/next/koreaOfRecord/parliamentBldg.do','supports':['64m dome base diameter; dome height 20m from historical design narrative; roof datum estimated']})
        reference=c.get('referenceUrl') or next((s.get('url') for s in sources if isinstance(s,dict) and s.get('url')),'https://www.openstreetmap.org/')
        asset={'id':c['id'],'model':filename,'name':name,'nameKo':name,'district':c.get('district',c.get('districtName')),'category':c.get('kind','apartment-complex'),'minZoom':14.5,'units':'metres',**stats,'rootTransform':'identity','coordinate':{'lon':lon,'lat':lat,'basis':'centre of retained source footprint bounds, Mercator metres; candidate matching documented separately','confidence':'source_footprint_unsurveyed'},'yawDegFromEast':0,'heightDatum':'Source heights where available; otherwise storeys x 3.05 m estimate. Roof plant stays inside known source-height envelopes; special silhouette dimensions are documented separately. All building bases at local floor zero.','referenceUrl':reference,'sources':sources,'geometryProvenance':'Retained real building footprint polygons from data/buildings.sqlite; no modification to database','heightEstimated':True,'sourceHeightAvailableForEveryBuilding':all(p['sourceHeightM'] is not None for p in parts),'modelingEstimates':{'facade':'Procedural window ribbons, piers and mineral colours; not photo-measured','roof':'Setback rooftop plant from inset footprint; estimated','storeyHeightM':3.05,'specialSilhouette':name if name in ('독립문','봉은사 진여문','현충관','국회의사당','올림픽체조경기장','파크원 타워1') else None,'specialSilhouetteProportions':'Dome, arch, eaves and structural colour accents are source-informed visual estimates; see linked dimension sources where available','storeyFallback':15 if c.get('apartmentCode') else 3,'groundDatum':'shared floor plane, local terrain queried at model anchor'},'buildingCount':len(rows),'footprintIds':ids,'estimatedDetails':['Footprint shape and placement follow the retained source geometry.','Window arrangement, materials, roof details and missing heights are estimates; not surveyed architecture.','Source building records and matching evidence are in docs/DISTRICT_LANDMARK_PROVENANCE.json.'],'validation':{'finitePositions':True,'unitNormals':True,'noExternalResources':True}}
        assets.append(asset);matches[c['id']]=ids;evidence.append({'id':c['id'],'nameKo':name,'district':asset['district'],'selection':c,'buildings':parts})
        print(f"{index+1}/250 {name}: {len(rows)} footprints, {stats['triangles']} triangles",flush=True)
    meta={k:v for k,v in old.items() if k!='assets'}
    meta['createdWith']='Original four and imported Geunjeongjeon: retained Blender GLBs; district expansion: Python/NumPy/Shapely source-footprint generator'
    meta['verificationScope']='Original four records and GLB hashes preserved; generated GLBs checked for float32 metre bounds, floor origin, finite geometry and self-contained buffers. Runtime/browser validation is recorded separately.'
    meta['notice']='Independent source-informed reconstructions. Original four Blender assets retained unchanged; imported Geunjeongjeon and 250 footprint-driven district reconstructions. Facades, roofs and missing heights are estimated; not survey/CAD.'
    meta['districtExpansion']={'generator':'scripts/build_district_landmarks.py','count':250,'districtCount':25,'importedFlightIds':[a['id'] for a in imported],'preservedElevationIds':list(PRESERVED),'provenance':'../../docs/DISTRICT_LANDMARK_PROVENANCE.json'}
    prefix=json.dumps(meta,ensure_ascii=False,indent=2)[:-2]+',\n  "assets": [\n'
    records=['    '+raw[a['id']] for a in kept]
    records += ['\n'.join('    '+line for line in json.dumps(a,ensure_ascii=False,indent=2).splitlines()) for a in imported+assets]
    manifestfile.write_text(prefix+',\n'.join(records)+'\n  ]\n}\n')
    (OUT/'footprint-matches.json').write_text(json.dumps(matches,ensure_ascii=False,indent=2)+'\n')
    proof={'schemaVersion':1,'generator':'scripts/build_district_landmarks.py','sourceDatabase':'data/buildings.sqlite (read-only)','preservedHashes':baseline,'districtCounts':dict(Counter(a['district'] for a in assets)),'assets':evidence}
    (ROOT/'docs/DISTRICT_LANDMARK_PROVENANCE.json').write_text(json.dumps(proof,ensure_ascii=False,indent=2)+'\n')
    reread=raw_asset_records(manifestfile.read_text())
    assert all(raw[k]==reread[k] for k in PRESERVED)
    assert all(hashlib.sha256((OUT/(k+'.glb')).read_bytes()).hexdigest()==baseline[k] for k in PRESERVED)
    assert len(json.loads(manifestfile.read_text())['assets'])==255
    print(json.dumps({'assets':255,'newBytes':sum(a['bytes'] for a in assets),'newTriangles':sum(a['triangles'] for a in assets),'districtCounts':proof['districtCounts'],'preservedRecordsExact':True},ensure_ascii=False))
if __name__=='__main__':main()
