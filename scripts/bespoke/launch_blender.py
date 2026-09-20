"""Start an isolated GUI Blender instance with a reviewed local MCP addon.

No existing scene, saved preferences or global MCP configuration is modified.
Model construction itself is sent through blender_mcp_client.py.
"""
import argparse, os, subprocess, tempfile
from pathlib import Path
p=argparse.ArgumentParser(description=__doc__)
p.add_argument('--addon',type=Path,required=True)
p.add_argument('--port',type=int,required=True)
p.add_argument('--blender',default='/Applications/Blender.app/Contents/MacOS/Blender')
a=p.parse_args()
if not a.addon.is_file() or not 1024<=a.port<=65535:raise SystemExit('Supply an existing addon and an unprivileged local port')
folder=Path(tempfile.mkdtemp(prefix='seoul-blender-'))
bootstrap=folder/'start.py'
bootstrap.write_text('''import bpy, importlib.util, sys
spec=importlib.util.spec_from_file_location('seoul_blender_mcp',%r)
addon=importlib.util.module_from_spec(spec)
sys.modules[spec.name]=addon
spec.loader.exec_module(addon)
addon.register()
bpy.context.scene.blendermcp_auto_start_server=False
bpy.context.scene.blendermcp_port=%d
bpy.types.blendermcp_server=addon.BlenderMCPServer(host='127.0.0.1',port=%d)
bpy.types.blendermcp_server.start()
bpy.context.scene.blendermcp_server_running=True
print('SEOUL_BLENDER_MCP_READY',%d,flush=True)
'''%(str(a.addon.resolve()),a.port,a.port,a.port))
with (folder/'blender.log').open('w') as log:
    process=subprocess.Popen([a.blender,'--factory-startup','--python',str(bootstrap)],
        env={**os.environ,'BLENDER_MCP_DISABLE_TELEMETRY':'1'},stdout=log,stderr=subprocess.STDOUT,start_new_session=True)
print({'pid':process.pid,'port':a.port,'log':str(folder/'blender.log')})
