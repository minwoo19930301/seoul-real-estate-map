import pathlib
P=pathlib.Path(__file__).parent
for t in [207, 208]:
 for script in ['build.py','check-standalone.py']:
  p=P/str(t)/script;exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
