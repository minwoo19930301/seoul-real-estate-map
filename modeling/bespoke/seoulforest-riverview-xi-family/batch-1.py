import pathlib
P=pathlib.Path(__file__).parent
for t in [101, 102]:
 p=P/str(t)/'build.py';exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
