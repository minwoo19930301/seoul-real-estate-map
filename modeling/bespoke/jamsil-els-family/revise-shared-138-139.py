import pathlib
P=pathlib.Path(__file__).parent
for t in [138,139]:
 for name in ['build.py','check-standalone.py']:
  p=P/str(t)/name;exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
