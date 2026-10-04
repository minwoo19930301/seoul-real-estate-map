from PIL import Image,ImageDraw
from pathlib import Path
P=Path(__file__).parent
for start in [130,135,140]:
 if not all((P/str(t)/'roof.png').exists() for t in range(start,start+5)):continue
 im=Image.new('RGB',(1100,1240),'white');draw=ImageDraw.Draw(im)
 for i,t in enumerate(range(start,start+5)):
  for j,v in enumerate(['front','opposite','side','roof']):
   a=Image.open(P/str(t)/(v+'.png'));a.thumbnail((220,280));im.paste(a,(i*220,j*310+20));draw.text((i*220+5,j*310+3),f'{t} {v}',fill='black')
 im.save(P/f'review-{start}-{start+4}.png')
