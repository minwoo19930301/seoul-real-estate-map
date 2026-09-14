import { homedir } from 'node:os';
import { join } from 'node:path';
import { existsSync } from 'node:fs';
process.env.SEOUL_TURSO_CONFIG ||= join(homedir(), '.config', 'seoul-map-turso', 'runtime.json');
if (!existsSync(process.env.SEOUL_TURSO_CONFIG)) {
  console.error('Turso runtime.json 설정 파일이 필요합니다. docs/TURSO.md를 확인하세요.');
  process.exit(1);
}
process.argv.push('--production');
await import('./dev.mjs');
