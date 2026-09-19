"""Source-outline civic silhouettes. All dimensions other than input outline/height
are visual estimates; see docs/CIVIC_MODEL_DESIGN.md. No builder dependency.
"""
import math
from shapely.geometry import Polygon, Point
from shapely.geometry.polygon import orient
from shapely.ops import triangulate, unary_union

STONE = [.65, .64, .59]
WOOD = [.43, .19, .12]
GREEN = [.20, .35, .29]
TILE = [.17, .21, .23]
GLASS = [.27, .42, .49]


def _polys(geom):
    if geom.is_empty:
        return []
    if geom.geom_type == 'Polygon':
        return [geom] if geom.area > 1e-7 else []
    return [p for g in getattr(geom, 'geoms', []) for p in _polys(g)]


class _Frame:
    def __init__(self, poly):
        pts = list(poly.convex_hull.exterior.coords)[:-1]
        best = None
        for a, b in zip(pts, pts[1:]+pts[:1]):
            length = math.dist(a,b)
            if length < 1e-9:
                continue
            ux,uz=(b[0]-a[0])/length,(b[1]-a[1])/length
            xs=[x*ux+z*uz for x,z in pts]
            zs=[-x*uz+z*ux for x,z in pts]
            lo,hi,near,far=min(xs),max(xs),min(zs),max(zs)
            item=((hi-lo)*(far-near),ux,uz,lo,hi,near,far)
            if best is None or item[0]<best[0]-1e-7:
                best=item
        _,ux,uz,lo,hi,near,far=best
        self.cx=ux*(lo+hi)/2-uz*(near+far)/2
        self.cz=uz*(lo+hi)/2+ux*(near+far)/2
        if hi-lo >= far-near:
            self.ux,self.uz,self.w,self.d=ux,uz,hi-lo,far-near
        else:
            self.ux,self.uz,self.w,self.d=-uz,ux,far-near,hi-lo

    def pos(self, x, y, z):
        return self.cx+self.ux*x-self.uz*z, y, self.cz+self.uz*x+self.ux*z

    def local(self, x, z):
        x, z = x-self.cx, z-self.cz
        return x*self.ux+z*self.uz, -x*self.uz+z*self.ux

    def rect(self, x0, z0, x1, z1):
        return Polygon([(self.pos(x, 0, z)[0], self.pos(x, 0, z)[2])
                        for x, z in [(x0,z0),(x1,z0),(x1,z1),(x0,z1)]])


def _solid(mesh, geom, bottom, top, color, roof=None):
    if top <= bottom:
        return
    for p in _polys(geom):
        mesh.solid(p, bottom, top, color, roof or color)


def _cap(mesh, geom, yfn, color, mat=2, reverse=False):
    for p in _polys(geom):
        for t in triangulate(p):
            if not p.covers(t):
                continue
            a, b, c = list(orient(t, 1).exterior.coords)[:3]
            vertices = [(x, yfn(x,z), z) for x,z in (a,c,b)]
            mesh.tri(mat, *(vertices[::-1] if reverse else vertices), color)


def _variable_solid(mesh, geom, bottomfn, topfn, color, mat=0):
    for p in _polys(geom):
        p = orient(p, 1)
        for ring in [p.exterior, *p.interiors]:
            pts = list(ring.coords)
            for a,b in zip(pts,pts[1:]):
                mesh.quad(mat, (a[0],bottomfn(*a),a[1]), (a[0],topfn(*a),a[1]),
                          (b[0],topfn(*b),b[1]), (b[0],bottomfn(*b),b[1]), color)
        _cap(mesh,p,topfn,color,mat)
        _cap(mesh,p,bottomfn,color,mat,True)


def _roof(mesh, poly, frame, base, peak, scale=1., gable=False):
    """Curved hip planes with raised eave corners, clipped to source roof outline."""
    w, d = frame.w*scale, frame.d*scale
    envelope = poly.intersection(frame.rect(-w/2,-d/2,w/2,d/2))
    rise = peak-base
    def yfn(x,z):
        x,z=frame.local(x,z)
        tx,tz=min(1,abs(x)/(w/2)),min(1,abs(z)/(d/2))
        slope = 1-tz if gable else min(1-tz,(1-tx)/.42)
        # Convex pitch and an upturned corner finish; never exceeds peak.
        return base+rise*min(1,max(0,slope)**1.55+.13*tx**8*tz**6)
    # Mesh subdivisions expose roof curvature and alternate subtle tile courses.
    nx,nz=30,16
    for i in range(nx):
        for j in range(nz):
            patch=frame.rect(w*(i/nx-.5),d*(j/nz-.5),w*((i+1)/nx-.5),d*((j+1)/nz-.5))
            col=[v+(0.025 if (i+j)%4 == 0 else 0) for v in TILE]
            _cap(mesh,envelope.intersection(patch),yfn,col)
    for p in _polys(envelope):
        pts=list(orient(p,1).exterior.coords)
        for a,b in zip(pts,pts[1:]):
            ya,yb=yfn(*a),yfn(*b)
            mesh.quad(2,(a[0],ya-rise*.06,a[1]),(a[0],ya,a[1]),
                      (b[0],yb,b[1]),(b[0],yb-rise*.06,b[1]),TILE)
    # A narrow, genuinely raised ridge, bounded by the input height.
    ridge=frame.rect(-w*(.47 if gable else .275),-d*.012,w*(.47 if gable else .275),d*.012)
    _solid(mesh,envelope.intersection(ridge),peak-rise*.035,peak,[.30,.33,.32])


def _columns(mesh,poly,frame,bottom,top,width=.77,depth=.67,bays=5):
    r=min(frame.d*.026,frame.w*.014)
    for side in [-1,1]:
        for i in range(bays+1):
            x=(i/bays-.5)*frame.w*width
            z=side*frame.d*depth/2
            p=frame.pos(x,0,z)
            foot=Point(p[0],p[2]).buffer(r,resolution=3).intersection(poly)
            _solid(mesh,foot,bottom,bottom+(top-bottom)*.08,STONE)
            _solid(mesh,foot,bottom+(top-bottom)*.08,top,WOOD)
            bracket=frame.rect(x-r*1.6,z-r*1.6,x+r*1.6,z+r*1.6).intersection(poly)
            _solid(mesh,bracket,top-(top-bottom)*.12,top,GREEN)


def _pavilion_core(poly, frame):
    """Inscribed rectangular pavilion estimate for gate + barbican outlines.

    The perimeter remains masonry. A bounded search finds the largest sampled
    rectangle wholly inside the source polygon; its width/depth caps prevent a
    long adjoining curtain wall from being interpreted as the wooden pavilion.
    """
    if poly.area/(frame.w*frame.d) >= .72:
        return poly, frame
    wcap,dcap=frame.w*.60,frame.d*.35
    candidates=[]
    for step in range(17):
        scale=1-step*.035
        w,d=wcap*scale,dcap*scale
        for i in range(33):
            x=(i/32-.5)*(frame.w-w)
            for j in range(33):
                z=(j/32-.5)*(frame.d-d)
                rectangle=frame.rect(x-w/2,z-d/2,x+w/2,z+d/2)
                if poly.covers(rectangle):
                    centre=rectangle.centroid
                    # Prefer the thick main base, then the centre of source mass.
                    score=(centre.distance(poly.boundary),-centre.distance(poly.centroid))
                    candidates.append((score,rectangle))
        if candidates:
            core=max(candidates,key=lambda item:item[0])[1]
            return core,_Frame(core)
    # A very fragmented outline has no safe large rectangular pavilion. Use the
    # widest eroded component as a conservative source-constrained fallback.
    parts=_polys(poly.buffer(-min(frame.d*.09,2.)))
    core=max(parts,key=lambda p:p.area) if parts else poly
    return core,_Frame(core)


def _gate(mesh,poly,f,height,big):
    pavilion,pf=_pavilion_core(poly,f) if big else (poly,f)
    f=pf
    plinth=height*(.41 if big else .48)
    r=min(f.w*.14,plinth*.37)
    spring=plinth*.35
    channel=f.rect(-r,-f.d,r,f.d)
    _solid(mesh,poly.difference(channel),0,plinth,STONE)
    # Each strip has an interpolated curved soffit, so the opening is a real
    # tunnel rather than a dark rectangle painted on a solid block.
    for i in range(24):
        x0,x1=-r+2*r*i/24,-r+2*r*(i+1)/24
        h0=spring+math.sqrt(max(0,r*r-x0*x0))
        h1=spring+math.sqrt(max(0,r*r-x1*x1))
        def low(x,z):
            t=max(0,min(1,(f.local(x,z)[0]-x0)/(x1-x0)))
            return h0+(h1-h0)*t
        patch=poly.intersection(f.rect(x0,-f.d,x1,f.d))
        _variable_solid(mesh,patch,low,lambda x,z:plinth,STONE)
    # A cap is above the opening, not at ground level.
    _solid(mesh,poly,plinth,plinth+height*.025,[.71,.70,.65])
    lower=f.rect(-f.w*.38,-f.d*.32,f.w*.38,f.d*.32).intersection(pavilion)
    eave=height*(.61 if big else .73)
    _solid(mesh,lower,plinth,eave,[.35,.18,.12])
    _columns(mesh,pavilion,f,plinth,eave,bays=5 if big else 3)
    if big:
        _roof(mesh,pavilion,f,eave,height*.80)
        upper=f.rect(-f.w*.31,-f.d*.25,f.w*.31,f.d*.25).intersection(pavilion)
        _solid(mesh,upper,height*.735,height*.825,WOOD)
        _columns(mesh,pavilion,f,height*.735,height*.835,width=.62,depth=.50,bays=5)
        _roof(mesh,pavilion,f,height*.825,height,scale=.84)
    else:
        _roof(mesh,poly,f,eave,height)


def _hall(mesh,poly,f,height,name):
    threshold=height*.075
    _solid(mesh,poly,0,threshold,STONE)
    openhall='함인정' in name or '일주문' in name or '선인문' in name
    eave=height*.62
    if not openhall:
        body=f.rect(-f.w*.38,-f.d*.33,f.w*.38,f.d*.33).intersection(poly)
        _solid(mesh,body,threshold,eave,[.64,.54,.39])
        _grid(mesh,body,threshold,eave,3,0,wood=True)
    bays=2 if '선인문' in name else 3 if '함인정' in name else 5
    _columns(mesh,poly,f,threshold,eave,bays=bays,depth=.62)
    beam=f.rect(-f.w*.42,-f.d*.35,f.w*.42,f.d*.35).intersection(poly)
    _solid(mesh,beam,eave-height*.05,eave,GREEN)
    _roof(mesh,poly,f,eave,height,gable=('판전' in name or '선인문' in name))


def _grid(mesh,poly,bottom,top,floors,seed,fins=False,wood=False,masonry=False):
    """Glazing lies on source edge; fins project inward to retain bounds."""
    for p in _polys(poly):
        p=orient(p,1)
        for ring in [p.exterior,*p.interiors]:
            pts=list(ring.coords)
            for a,b in zip(pts,pts[1:]):
                length=math.dist(a,b)
                if length<.8:
                    continue
                ux,uz=(b[0]-a[0])/length,(b[1]-a[1])/length
                nx,nz=uz,-ux
                bays=max(1,min(56,math.ceil(length/(1.6 if fins else 3.1))))
                levels=max(1,min(40,int(floors)))
                for i in range(bays):
                    for j in range(levels):
                        lo=bottom+(top-bottom)*(j+.13)/levels
                        hi=bottom+(top-bottom)*(j+.86)/levels
                        margin=.27 if masonry else .09
                        l=(i+margin)*length/bays; r=(i+1-margin)*length/bays
                        col=[.27,.31,.25] if wood else [.30,.45,.50] if (i+j+seed)%7 else [.44,.57,.61]
                        def q(t,y):
                            offset=-.22 if fins else .006
                            return(a[0]+ux*t+nx*offset,y,a[1]+uz*t+nz*offset)
                        mesh.quad(1,q(l,lo),q(l,hi),q(r,hi),q(r,lo),col)
                    if fins:
                        t=(i+.02)*length/bays
                        p0=(a[0]+ux*t,a[1]+uz*t)
                        thick=min(.20,length/bays*.11)
                        # 3-D fin on source boundary, extending into the glazing skin.
                        fp=Polygon([p0,(p0[0]+ux*thick,p0[1]+uz*thick),
                                    (p0[0]+ux*thick-nx*.42,p0[1]+uz*thick-nz*.42),
                                    (p0[0]-nx*.42,p0[1]-nz*.42)])
                        _solid(mesh,fp.intersection(poly),bottom,top,[.76,.76,.70])


def _office(mesh,poly,f,height,floors,seed,amore=False):
    body=[.32,.41,.44] if seed%2 else [.40,.47,.50]
    if amore and f.d>15 and f.w/f.d<1.8 and poly.area/(f.w*f.d)>.70:
        # Source holes are retained. New void position is an explicit estimate.
        court=f.rect(-f.w*.205,-f.d*.205,f.w*.205,f.d*.205)
        ring=poly.difference(court)
        cuts=unary_union([f.rect(-f.w*.14,-f.d,f.w*.14,0),
                          f.rect(-f.w,-f.d*.12,0,f.d*.12),
                          f.rect(-f.w*.14,0,f.w*.14,f.d)])
        sections=[(poly,0,.18),(ring,.18,.39),(ring.difference(cuts),.39,.65),(ring,.65,1)]
        for geom,lo,hi in sections:
            skin=geom.buffer(-min(.24,f.d*.01))
            _solid(mesh,skin if not skin.is_empty else geom,height*lo,height*hi,body,[.63,.64,.59])
            _grid(mesh,geom,height*lo,height*hi,max(1,round(floors*(hi-lo))),seed,True)
        # Gardens occupy the lower face of the openings, inside original outline.
        _cap(mesh,poly.intersection(cuts).difference(court),lambda x,z:height*.39+.012,[.30,.40,.27])
    else:
        fin_skin=amore or seed%3 == 0
        skin=poly.buffer(-.24) if fin_skin else poly
        _solid(mesh,skin if not skin.is_empty else poly,0,height,body,[.48,.52,.52])
        _grid(mesh,poly,0,height,floors,seed,fins=amore or seed%3 == 0)
        # Inset crown and mechanical screen, all below the height envelope.
        inset=poly.buffer(-min(f.d*.08,2.))
        if not inset.is_empty:
            _solid(mesh,poly.difference(inset),height*.97,height,[.66,.68,.66])


def _library(mesh,poly,f,height):
    bodytop=height*.79
    entry=f.rect(-f.w*.115,f.d*.20,f.w*.115,f.d*.55).intersection(poly)
    _solid(mesh,poly.difference(entry),0,height*.51,[.70,.69,.64],[.45,.47,.44])
    _solid(mesh,poly,height*.51,bodytop,[.70,.69,.64],[.45,.47,.44])
    _grid(mesh,poly.difference(entry),0,height*.51,2,0,masonry=True)
    _grid(mesh,poly,height*.51,bodytop,1,0,masonry=True)
    for frac in [.13,.39,.66,.77]:
        inner=poly.buffer(-min(.25,f.d*.03))
        band=poly.difference(inner)
        if frac<.51:band=band.difference(entry)
        _solid(mesh,band,height*frac,height*(frac+.022),[.80,.78,.71])
    # The principal entrance faces local +z; orientation is documented estimate.
    _solid(mesh,entry,0,height*.07,[.76,.74,.68])
    for i in range(6):
        x=f.w*(-.105+i*.042)
        p=f.pos(x,0,f.d*.43)
        col=Point(p[0],p[2]).buffer(min(f.w*.009,f.d*.025),resolution=4).intersection(poly)
        _solid(mesh,col,height*.07,height*.47,[.78,.76,.69])
    _solid(mesh,entry,height*.47,height*.51,[.79,.77,.70])
    clockblock=f.rect(-f.w*.075,f.d*.19,f.w*.075,f.d*.48).intersection(poly)
    _solid(mesh,clockblock,bodytop,height,[.72,.71,.66])
    # Round clock face, tick marks and two static illustrative hands (no logo).
    r=min(f.w*.033,height*.074);cy=height*.885;z=f.d*.481
    for i in range(48):
        t,u=math.tau*i/48,math.tau*(i+1)/48
        mesh.tri(0,f.pos(0,cy,z),f.pos(r*math.sin(u),cy+r*math.cos(u),z),
                 f.pos(r*math.sin(t),cy+r*math.cos(t),z),[.85,.86,.78])
    for i in range(12):
        t=math.tau*i/12
        x,y=r*.83*math.sin(t),cy+r*.83*math.cos(t)
        s=r*.035
        mesh.quad(0,f.pos(x+s,y-s,z+.006),f.pos(x+s,y+s,z+.006),
                  f.pos(x-s,y+s,z+.006),f.pos(x-s,y-s,z+.006),[.18,.26,.25])
    for t,size in [(0,.60),(math.pi*.62,.72)]:
        x,y=r*size*math.sin(t),cy+r*size*math.cos(t)
        s=r*.035
        mesh.quad(0,f.pos(s,cy,z+.01),f.pos(x+s,y,z+.01),
                  f.pos(x-s,y,z+.01),f.pos(-s,cy,z+.01),[.16,.23,.23])


def _cityhall(mesh,poly,f,height):
    # A sampled glass shell drapes over source polygon; no bounding-box tower.
    def yfn(x,z):
        u,v=f.local(x,z)
        a=max(-1,min(1,u/(f.w*.5)));b=max(-1,min(1,v/(f.d*.5)))
        return height*(.71+.29*(1-a*a)*math.cos(b*math.pi*.33))
    _variable_solid(mesh,poly,lambda x,z:0,yfn,[.34,.48,.53],1)
    for i in range(32):
        for j in range(16):
            patch=f.rect(f.w*(i/32-.5),f.d*(j/16-.5),f.w*((i+1)/32-.5),f.d*((j+1)/16-.5))
            col=[.39,.54,.59] if (i+j)%3 else [.54,.65,.68]
            _cap(mesh,poly.intersection(patch),yfn,col,1)
    # Mullion strips run over curved top and down perimeter.
    for i in range(33):
        x=f.w*(i/32-.5);s=min(.16,f.w*.0015)
        strip=poly.intersection(f.rect(x-s,-f.d,x+s,f.d))
        _cap(mesh,strip,lambda x,z:min(height,yfn(x,z)+.016),[.76,.79,.77],0)
    _grid(mesh,poly,0,height*.68,12,0)


def civic_geometry(mesh, poly, name, height, floors, seed):
    """Append known civic geometry and return True, or False without mutation.

    Input: valid metre Polygon, local floor 0, positive height envelope, storeys.
    Caller resolves absent source heights. Uses only Mesh.solid/tri/quad, mats 0–2.
    """
    name=''.join(str(name).split())
    if poly.is_empty or poly.geom_type!='Polygon' or not poly.is_valid or poly.area<1e-5:
        return False
    if not math.isfinite(height) or height<=0:
        return False
    big=any(n in name for n in ('숭례문','흥인지문'))
    gate=big or '건춘문' in name
    hall=any(n in name for n in ('함인정','조계사일주문','봉은사대웅전','봉은사판전','창경궁선인문'))
    library=name in ('서울도서관','서울시청구청사','서울특별시청구청사')
    cityhall=name in ('서울특별시청','서울시청','서울시청신청사','서울특별시청신청사')
    company=any(n in name.lower() for n in ('아모레퍼시픽','삼성전자','삼성생명','삼성화재','삼성물산',
        '삼성서초','삼성타운','삼성본관','sk서린','sk텔레콤','sk본사','sk그린','sk스퀘어',
        'skt타워','t타워','lg트윈','lg전자','lg유플러스','현대자동차','현대건설','현대해상',
        '기아본사','한화','롯데월드타워','롯데케미칼','롯데본사','포스코','두산','cj제일제당','cj본사',
        'cjthecenter','gs타워','kt광화문','ktwest','kteast','kt본사','교보생명','네이버','카카오'))
    if not any((gate,hall,library,cityhall,company)):
        return False
    f=_Frame(poly)
    if gate:_gate(mesh,poly,f,height,big)
    elif hall:_hall(mesh,poly,f,height,name)
    elif library:_library(mesh,poly,f,height)
    elif cityhall:_cityhall(mesh,poly,f,height)
    else:_office(mesh,poly,f,height,max(1,int(floors or 1)),int(seed),amore='아모레퍼시픽' in name)
    return True
