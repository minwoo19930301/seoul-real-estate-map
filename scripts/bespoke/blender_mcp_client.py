"""Run an inspected site-specific script through the real Blender MCP server.

Use a separate localhost Blender/addon port for each artist. The MCP server
executable is supplied by the caller; this does not change any app MCP config.
"""
import argparse, asyncio, base64, json, os, sys
from datetime import timedelta
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

async def run(args):
    env = {key: os.environ[key] for key in ['PATH', 'HOME', 'LANG'] if key in os.environ}
    env['BLENDER_MCP_DISABLE_TELEMETRY'] = '1'
    params = StdioServerParameters(command=args.server, args=['--host', '127.0.0.1', '--port', str(args.port)], env=env)
    prompt = Path(args.prompt_file).read_text() if args.prompt_file else '템플릿으로 공장처럼 찍지 말고.'
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write, read_timeout_seconds=timedelta(seconds=240)) as session:
            await session.initialize()
            if args.action == 'inspect':
                calls = [('get_addon_status', {'user_prompt': prompt}), ('get_scene_info', {'user_prompt': prompt})]
            elif args.action == 'execute':
                if not args.script: raise SystemExit('--script is required')
                script = Path(args.script).resolve()
                code = '__file__ = ' + repr(str(script)) + '\n' + script.read_text()
                calls = [('execute_blender_code', {'code': code, 'user_prompt': prompt})]
            elif args.action == 'screenshot':
                if not args.output: raise SystemExit('--output is required')
                calls = [('get_viewport_screenshot', {'max_size': 1400, 'user_prompt': prompt})]
            results = []
            for name, arguments in calls:
                result = await session.call_tool(name, arguments, read_timeout_seconds=timedelta(seconds=240))
                content = []
                for item in result.content:
                    if item.type == 'image':
                        out = Path(args.output); out.parent.mkdir(parents=True, exist_ok=True)
                        out.write_bytes(base64.b64decode(item.data))
                        content.append({'type': 'image', 'path': str(out), 'mimeType': item.mimeType})
                    elif item.type == 'text': content.append({'type': 'text', 'text': item.text})
                record = {'tool': name, 'port': args.port, 'isError': result.isError, 'content': content}
                results.append(record)
                print(json.dumps(record, ensure_ascii=False))
                if result.isError or any(i.get('text', '').startswith(('Error executing code:', 'Rejected by safe mode')) for i in content):
                    raise SystemExit(1)
            if args.record:
                out = Path(args.record); out.parent.mkdir(parents=True, exist_ok=True)
                out.write_text(json.dumps(results, ensure_ascii=False, indent=2)+'\n')

if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('action', choices=['inspect', 'execute', 'screenshot'])
    p.add_argument('--port', type=int, required=True)
    p.add_argument('--server', default='/tmp/seoul-blender-mcp-env/bin/mcp-for-blender')
    p.add_argument('--script'); p.add_argument('--output'); p.add_argument('--record'); p.add_argument('--prompt-file')
    asyncio.run(run(p.parse_args()))
