import pathlib
P=pathlib.Path(__file__).parent
for name in ['build.py','check-standalone.py']:
 p=P/'109'/name;exec(compile(p.read_text(),str(p),'exec'),{'__file__':str(p)})
