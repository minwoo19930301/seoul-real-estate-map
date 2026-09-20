from pathlib import Path
REVIEW_VIEWS=['A_SE_primary_match', 'W05_north_coplanar_end', 'NE_end_detail', 'NW_core_courtyard']
exec(compile((Path(__file__).parent/"render.py").read_text(),"render.py","exec"))
