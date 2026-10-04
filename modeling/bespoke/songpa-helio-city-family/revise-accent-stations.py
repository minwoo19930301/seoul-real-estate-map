from pathlib import Path
import json,shutil
P=Path(__file__).parent
old='[(.30,3),(.64,4),(.45,6),(.30,8),(.64,9)]';new='[(.30,round(FLOORS*.25)),(.64,round(FLOORS*.33)),(.45,round(FLOORS*.50)),(.30,round(FLOORS*.67)),(.64,round(FLOORS*.75))]'
for n in range(101,111):
 q=P/str(n)
 if (q/f'songpa-helio-city-{n}.glb').exists():
  ar=q/'archive-initial-accent-stations';ar.mkdir()
  for p in q.iterdir():
   if p.is_file():shutil.copy2(p,ar/p.name)
 p=q/'build.py';p.write_text(p.read_text().replace(old,new));p=q/'source-data.json';d=json.loads(p.read_text());d['accent_station_basis']='Five sparse short orange accents at own floor fractions25/33/50/67/75 percent, inferred from representative, not measured.';d['reference_scope']+=' Short orange accent stations use own floor fractions25/33/50/67/75 percent, inferred.';p.write_text(json.dumps(d,ensure_ascii=False,indent=2))
p=P/'prepare-family.py';s=p.read_text().replace(" (P/'build.py').write_text(s)"," s=s.replace("+repr(old)+","+repr(new)+")\n (P/'build.py').write_text(s)");p.write_text(s)
