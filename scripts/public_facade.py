"""Source-footprint school/office facade detailing; materials and entrance placement are estimates."""
import math
from shapely.geometry import Polygon
from shapely.geometry.polygon import orient

def public_facade(mesh,poly,height,floors,kind):
    school=kind=='k12-school';floors=max(1,min(25,int(floors)));poly=orient(poly,sign=1)
    wall=[.83,.80,.72] if school else [.73,.77,.78];brick=[.48,.30,.23] if school else [.44,.49,.51]
    glass=[.23,.37,.43];frame=[.81,.83,.80];roof=[.46,.49,.46]
    parapet=min(.65,height*.04);body=height-parapet
    mesh.solid(poly,0,body,wall,roof)
    # Actual footprint is preserved; inset parapet follows its concave perimeter.
    inner=poly.buffer(-.30)
    band=poly.difference(inner) if not inner.is_empty else poly
    for ring in [band] if band.geom_type=='Polygon' else list(band.geoms):mesh.solid(ring,body,height,wall,roof)
    spacing=body/floors;longest=None
    for ring in [poly.exterior,*poly.interiors]:
        pts=list(ring.coords)
        for (x,z),(u,v) in zip(pts,pts[1:]):
            dx,dz=u-x,v-z;length=math.hypot(dx,dz)
            if length<3:continue
            ux,uz=dx/length,dz/length;nx,nz=uz,-ux
            def q(t,y,offset=.045):return(x+ux*t+nx*offset,y,z+uz*t+nz*offset)
            # Brick plinth, individual framed panes, and horizontal slab lines.
            mesh.quad(0,q(0,.15),q(0,min(1.05,body)),q(length,min(1.05,body)),q(length,.15),brick)
            bays=max(1,min(35,int((length-1)/3.0)));pitch=(length-1)/bays
            for floor in range(floors):
                bottom=floor*spacing+spacing*.30;top=min(body-.25,bottom+spacing*.53)
                if top<=bottom:continue
                for j in range(bays):
                    a=.5+j*pitch+pitch*.13;b=.5+(j+1)*pitch-pitch*.13
                    mesh.quad(0,q(a-.10,bottom-.10),q(a-.10,top+.10),q(b+.10,top+.10),q(b+.10,bottom-.10),frame)
                    mesh.quad(1,q(a,bottom,.06),q(a,top,.06),q(b,top,.06),q(b,bottom,.06),glass)
                    mid=(a+b)/2
                    mesh.quad(0,q(mid-.035,bottom,.08),q(mid-.035,top,.08),q(mid+.035,top,.08),q(mid+.035,bottom,.08),frame)
                y=min(body-.1,(floor+1)*spacing-.13)
                mesh.quad(0,q(0,y,.07),q(0,y+.10,.07),q(length,y+.10,.07),q(length,y,.07),frame)
            if ring==poly.exterior and (longest is None or length>longest[0]):longest=(length,x,z,ux,uz,nx,nz)
    if longest and longest[0]>9:
        length,x,z,ux,uz,nx,nz=longest;middle=length*.5;w=min(5,length*.2);h=min(3.2,body*.8)
        def p(t,y,o):return(x+ux*t+nx*o,y,z+uz*t+nz*o)
        mesh.quad(1,p(middle-w/2,.1,.1),p(middle-w/2,h,.1),p(middle+w/2,h,.1),p(middle+w/2,.1,.1),glass)
        # A modest entrance canopy, explicitly approximate; not a surveyed entrance location.
        a,b,c,d=[p(t,h+.25,o) for t,o in [(middle-w/2-.4,0),(middle+w/2+.4,0),(middle+w/2+.4,1.2),(middle-w/2-.4,1.2)]]
        mesh.quad(2,a,d,c,b,brick)
