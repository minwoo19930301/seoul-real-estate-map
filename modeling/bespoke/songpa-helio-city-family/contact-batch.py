from pathlib import Path
from PIL import Image,ImageDraw
import sys,json,hashlib
P=Path(__file__).parent;nums=list(map(int,sys.argv[1:]));files=[]
for a,b in zip(nums[::2],nums[1::2]):
 out=Image.new('RGB',(1200,800),'white');draw=ImageDraw.Draw(out)
 for row,n in enumerate([a,b]):
  for col,v in enumerate(['front','opposite','side','roof']):
   im=Image.open(P/str(n)/(v+'.png')).convert('RGB');im.thumbnail((300,375));out.paste(im,(col*300+(300-im.width)//2,row*400+25));draw.text((col*300+8,row*400+6),f'{n} {v}',fill='black')
 q=P/f'contact-{a}-{b}.jpg';out.save(q,quality=95);files.append(q)
p=P/f'hashes-{nums[0]}-{nums[-1]}.json';d=json.loads(p.read_text());d.update({q.name:hashlib.sha256(q.read_bytes()).hexdigest() for q in files});p.write_text(json.dumps(d,indent=2))
