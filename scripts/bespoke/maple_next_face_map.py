"""Copyright-free own edge/wingdiagram derived from retained numbered footprints."""
import json
from pathlib import Path
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[2];OUT=ROOT/'data/model-source/bespoke/maple-next-towers';D=json.loads((OUT/'authored-input.json').read_text());im=Image.new('RGB',(1400,1100),'#f4f3ef');dr=ImageDraw.Draw(im);font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',25);sm=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',18)
dr.text((40,24),'MAPLE XI - INDIVIDUAL EDGE AND ROOF MAPPING',font=font,fill='#263540');dr.text((40,64),'North up. Edge e_i runs from v_i to v_i+1. Height numbers are estimates, not verified storeys.',font=sm,fill='#263540')
for i,a in enumerate(D['assets']):
 ox=350+(i%2)*670;oy=310+(i//2)*480;pts=[(ox+x*7,oy-y*7) for x,y in a['ring']];dr.polygon(pts,fill='#dce2e1',outline='#3a4b55',width=3)
 if len(pts)==6:
  dr.line([pts[2],pts[5]],fill='#a79571',width=3);w0=[pts[k] for k in [0,1,2,5]];w1=[pts[k] for k in [2,3,4,5]]
  for wi,w in enumerate([w0,w1]):dr.text((sum(x for x,y in w)/4-28,sum(y for x,y in w)/4-8),str(a['roof']['heights'][wi])+'m',font=sm,fill='#4f5e64')
 else:dr.text((ox-33,oy-9),str(a['roof']['heights'][0])+'m',font=sm,fill='#4f5e64')
 for j,(p,q) in enumerate(zip(pts,pts[1:]+pts[:1])):
  kind=a['faces'][j]['kind'];col='#28737b' if kind=='curtain-look' else '#934e38' if kind=='painted-dark' else '#3a4b55';dr.line([p,q],fill=col,width=5);x,y=(p[0]+q[0])/2,(p[1]+q[1])/2;vx,vy=q[0]-p[0],q[1]-p[1];le=(vx*vx+vy*vy)**.5;dr.text((x+vy/le*23-12,y-vx/le*23-10),'e'+str(j),font=sm,fill=col);dr.text((p[0]+3,p[1]+3),'v'+str(j),font=sm,fill='#3a4b55')
 dr.text((ox-270,oy-175),str(a['dong']),font=font,fill='#263540');dr.text((ox-295,oy+170),a['roof']['description'].split(';')[0][:70],font=sm,fill='#3a4b55')
dr.text((40,1035),'Teal:208 e1 /212 e3 curtain-wall-look. Brown:213 e3 painted dark wall with separate windows.',font=sm,fill='#263540');dr.text((40,1063),'208 e2 /212 e4 /213 e4: white grids;209 e4 bright with narrow middle slots. 208 entry orientation and hidden faces remain provisional.',font=sm,fill='#263540');im.save(OUT/'face-map.png')
