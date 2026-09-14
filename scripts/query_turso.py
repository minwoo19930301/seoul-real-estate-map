"""Query an uploaded district source shard with its server-side read token."""
import argparse, json, sys
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from server.database import Connection

def main():
 p=argparse.ArgumentParser();p.add_argument('--district',required=True,help='gangnam, seocho, shared, etc.');p.add_argument('--sql',required=True);args=p.parse_args()
 state=json.loads((Path.home()/'.config/seoul-map-turso/upload-state.json').read_text())
 item=state['seoul-source-'+args.district+'.sqlite']
 with Connection({'hostname':item['hostname'],'token':item['read_token'],'metadata_table':'metadata'}) as c:
  rows=[dict(r) for r in c.execute(args.sql)]
 print(json.dumps(rows,ensure_ascii=False,indent=2,default=lambda x:x.hex() if isinstance(x,bytes) else str(x)))
if __name__=='__main__':main()
