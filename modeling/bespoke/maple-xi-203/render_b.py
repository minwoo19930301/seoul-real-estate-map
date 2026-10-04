from pathlib import Path
REVIEW_VIEWS=['Roof_three_individual_plants', 'Ground_NE_stone', 'Inner_L_core', 'SE_window_depth_detail']
exec((Path(__file__).parent/'render.py').read_text())
