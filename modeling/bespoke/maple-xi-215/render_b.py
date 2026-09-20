from pathlib import Path
REVIEW_VIEWS=['Ground_NE_stone', 'SW_unverified_return', 'SE_white_detail', 'W06_NE_detail']
exec(compile((Path(__file__).parent/"render.py").read_text(),"render.py","exec"))
