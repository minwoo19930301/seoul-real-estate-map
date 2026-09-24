from pathlib import Path
REVIEW_VIEWS=['B_south_primary_match', 'A_east_primary_match', 'W41_North_end', 'W43_East_corner']
exec((Path(__file__).parent/'render.py').read_text())
