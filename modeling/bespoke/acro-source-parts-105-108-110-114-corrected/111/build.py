from pathlib import Path
recipe=Path(__file__).parent.parent/'build_region_model.py'
exec(compile(recipe.read_text(),str(recipe),'exec'))
