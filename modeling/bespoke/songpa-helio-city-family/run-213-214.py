import pathlib
P=pathlib.Path(__file__).parent
for n in [213,214]:
 for name in ["build.py","check-standalone.py"]:
  p=P/str(n)/name;exec(compile(p.read_text(),str(p),"exec"),{"__file__":str(p)})
