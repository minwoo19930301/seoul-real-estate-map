from pathlib import Path
NUMBER=205
exec(compile((Path(__file__).parent/'build.py').read_text(),str(Path(__file__).parent/'build.py'),'exec'))
