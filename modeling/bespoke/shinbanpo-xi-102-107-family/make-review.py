from PIL import Image,ImageDraw
from pathlib import Path
P=Path(__file__).parent
for start in [102,105]:
 im=Image.new('RGB',(900,1440),'white');dr=ImageDraw.Draw(im)
 for i,t in enumerate(range(start,start+3)):
  for j,v in enumerate(['front','opposite','side','roof']):
   a=Image.open(P/str(t)/(v+'.png'));a.thumbnail((300,330));im.paste(a,(i*300,j*360+25));dr.text((i*300+5,j*360+5),f'{t} {v}',fill='black')
 im.save(P/f'review-{start}-{start+2}.png')
