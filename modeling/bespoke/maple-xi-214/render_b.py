from pathlib import Path
REVIEW_VIEWS=['Roof_two_individual_plants', 'Ground_north_stone', 'SW_unverified_return', 'SE_primary_detail']
exec(compile((Path(__file__).parent/"render.py").read_text(),"render.py","exec"))
