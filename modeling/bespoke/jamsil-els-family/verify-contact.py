import pathlib,json,runpy,contextlib,io,sys
from PIL import Image,ImageDraw
P=pathlib.Path(__file__).parent;T=[int(x) for x in sys.argv[1:]]
for t in T:
 p=P/str(t);assert (p/'standalone-validation.json').exists()
 with contextlib.redirect_stdout(io.StringIO()):runpy.run_path(str(p/'validate.py'))
 d=json.loads((p/'geometry-proof.json').read_text());print(t,d['height_m'],d['floors'],d['triangle_count'],(p/f'jamsil-els-{t}.glb').stat().st_size)
for k in range(0,len(T),2):
 ts=T[k:k+2];c=Image.new('RGB',(1200,400*len(ts)),'#eeeeee');dr=ImageDraw.Draw(c)
 for r,t in enumerate(ts):
  for j,v in enumerate(['front','opposite','side','roof']):
   im=Image.open(P/str(t)/(v+'.png')).convert('RGB');im.thumbnail((300,370));c.paste(im,(j*300+(300-im.width)//2,r*400+24));dr.text((j*300+8,r*400+7),f'{t} {v}',fill='black')
 c.save(P/f'review-{ts[0]}-{ts[-1]}.png')
