import { spawn } from 'node:child_process';
import { existsSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import net from 'node:net';

const root = fileURLToPath(new URL('../', import.meta.url));
const python = [process.env.SEOUL_PYTHON, resolve(root, '.venv/bin/python'), resolve(root, '.venv-terrain/bin/python'), resolve(root, '../seoul-contours-feasibility/.venv-gis/bin/python')].find(p => p && existsSync(p));
if (!python || (!process.env.SEOUL_TURSO_CONFIG && !existsSync(resolve(root, 'data/terrain.sqlite')))) {
  console.error('먼저 README의 로컬 데이터 준비 단계를 실행해 주세요. Python 환경과 data/terrain.sqlite가 필요합니다.');
  process.exit(1);
}
const checkPort = port => new Promise((accept, reject) => {
  const probe = net.createServer();
  probe.once('error', reject);
  probe.listen(port, '127.0.0.1', () => probe.close(accept));
});
try { await checkPort(8791); await checkPort(4173); }
catch (error) { console.error('로컬 포트 4173 또는 8791이 이미 사용 중입니다.', error.message); process.exit(1); }

const children = [];
let stopping = false;
function stop(code = 0) {
  if (stopping) return;
  stopping = true;
  for (const child of children) child.kill('SIGTERM');
  setTimeout(() => process.exit(code), 300).unref();
}
function run(command, args) {
  const child = spawn(command, args, { cwd: root, stdio: 'inherit', env: { ...process.env, PYTHONUNBUFFERED: '1' } });
  children.push(child);
  child.on('error', error => { console.error(error.message); stop(1); });
  child.on('exit', code => { if (!stopping) stop(code ?? 1); });
  return child;
}
process.on('SIGINT', () => stop());
process.on('SIGTERM', () => stop());
run(python, ['-m', 'server.app', '--port', '8791']);
let ready = false;
for (let attempt = 0; attempt < 50 && !stopping; attempt++) {
  try { const response = await fetch('http://127.0.0.1:8791/api/health'); if (response.ok) { ready = true; break; } } catch {}
  await new Promise(accept => setTimeout(accept, 200));
}
if (!ready) { console.error('로컬 API 서버 시작을 확인하지 못했습니다.'); stop(1); }
else if (process.argv.includes('--production')) run(python, ['-m', 'server.app', '--port', '4173']);
else run(process.execPath, ['node_modules/vite/bin/vite.js', '--host', '127.0.0.1', '--port', '4173', '--strictPort']);
