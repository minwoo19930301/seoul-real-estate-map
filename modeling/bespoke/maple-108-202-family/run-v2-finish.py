from pathlib import Path
import subprocess,sys
O=Path(__file__).parent
for n in [113,114,201,202]:
 for action in ['build','validate','render']:
  script=O/f'build-{n}.py' if action=='build' else O/f'{action}.py'
  with (O/f'mcp-{action}-{n}-client.log').open('w') as log:
   result=subprocess.run(['/tmp/seoul-blender-mcp-env/bin/python','scripts/bespoke/blender_mcp_client.py','execute','--port','9878','--script',str(script),'--record',str(O/f'mcp-{action}-{n}.json')],stdout=log,stderr=subprocess.STDOUT)
  print(n,action,result.returncode,flush=True)
  if result.returncode:sys.exit(result.returncode)
