from pathlib import Path
from PIL import Image,ImageDraw
O=Path(__file__).parent
for p in sorted(O.glob('input-*.json')):
 n=int(p.stem.split('-')[-1])
 if not all((O/f'{n}-{v}.png').exists()for v in ['street','roof','opposite','close']):continue
 im=Image.new('RGB',(1152,1504),'#eeeeee');d=ImageDraw.Draw(im)
 for j,v in enumerate(['street','roof','opposite','close']):
  x=(j%2)*576;y=(j//2)*752;d.text((x+10,y+8),f'MAPLE {n} V2 | {v.upper()} | FAMILY INFERENCE',fill='black');im.paste(Image.open(O/f'{n}-{v}.png').resize((576,720)),(x,y+32))
 im.save(O/f'review-{n}.jpg',quality=93)
