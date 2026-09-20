"""Own numbered plan drawing; no reference photography copied into repository."""
import json,math
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-club-cloud';D=json.loads((OUT/'authored-input.json').read_text())
im=Image.new('RGB',(1200,850),'#f4f3ef');dr=ImageDraw.Draw(im);font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',22);small=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',17)
anchor=D['assets'][0]['coordinate']
project=lambda x,y:(360+x*9,445-y*9)
for a in D['assets']:
 dx=(a['coordinate']['lon']-anchor['lon'])*111320*math.cos(math.radians(anchor['lat']));dy=(a['coordinate']['lat']-anchor['lat'])*111320
 pts=[project(x+dx,y+dy) for x,y in a['ring']];dr.polygon(pts,fill='#dbe1e3',outline='#384855',width=3)
 for i,(p,q) in enumerate(zip(pts,pts[1:]+pts[:1])):
  selected=(a['dong']==210 and i==2) or (a['dong']==211 and i==4)
  dr.line([p,q],fill='#bd342d' if selected else '#384855',width=7 if selected else 3)
  vx,vy=q[0]-p[0],q[1]-p[1];ln=math.hypot(vx,vy);mx,my=(p[0]+q[0])/2,(p[1]+q[1])/2
  dr.text((mx+vy/ln*24-14,my-vx/ln*24-10),f'e{i}',font=font,fill='#bd342d' if selected else '#384855')
  dr.ellipse((p[0]-4,p[1]-4,p[0]+4,p[1]+4),fill='#222222');dr.text((p[0]+5,p[1]+5),f'v{i}',font=small,fill='#384855')
 x=sum(p[0] for p in pts)/len(pts);y=sum(p[1] for p in pts)/len(pts);dr.text((x-25,y-14),str(a['dong']),font=font,fill='#1e303e')
dr.text((38,26),'MAPLE XI 210 / 211 - PHOTO FACE MAPPING',font=font,fill='#1e303e')
dr.text((38,65),'Red: completed-photo visible faces; numbered vertices follow retained footprint order.',font=small,fill='#384855')
dr.text((38,680),'210 e2: southeast end, six broad window columns. e1: northeast return, provisional.',font=small,fill='#384855')
dr.text((38,715),'211 e4: pale left field, small openings, unequal gray stacks, dark right group.',font=small,fill='#384855')
dr.text((38,750),'Photo left -> right reverses the canonical e2/e4 edge direction. North is up.',font=small,fill='#384855')
dr.text((38,785),'Visual inference from official numbered plan + aerial; not surveyed correspondence.',font=small,fill='#384855')
im.save(OUT/'face-map.png')
