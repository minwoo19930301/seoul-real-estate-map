import pathlib,subprocess,sys
P=pathlib.Path(__file__).parent
for i in range(1,6):
 with (P/f'execution-batch-{i}.log').open('w') as log:
  r=subprocess.run(['/tmp/seoul-blender-mcp-env/bin/python','scripts/bespoke/blender_mcp_client.py','execute','--port','9878','--script',str(P/f'build-batch-{i}.py'),'--record',str(P/f'mcp-build-batch-{i}.json')],stdout=log,stderr=subprocess.STDOUT)
 if r.returncode:raise SystemExit(f'batch{i} failed; inspect before retry')
 print(f'Actual MCP batch{i} complete',flush=True)
