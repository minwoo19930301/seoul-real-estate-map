from pathlib import Path
REVIEW_VIEWS=['A_SE_primary_match', 'W06_North_end', 'W07_East_corner', 'Roof_individual_layout']
exec(compile((Path(__file__).parent/"render.py").read_text(),"render.py","exec"))
