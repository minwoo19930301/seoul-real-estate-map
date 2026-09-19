import { defineConfig } from 'vite';
import { readdir, readFile, writeFile } from 'node:fs/promises';
import { join } from 'node:path';
import { gzipSync } from 'node:zlib';

async function precompress(directory: string) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name);
    if (entry.isDirectory()) await precompress(path);
    else if (/\.(js|css|json|geojson|glb)$/.test(entry.name)) {
      const bytes = await readFile(path);
      if (bytes.length > 1024) await writeFile(`${path}.gz`, gzipSync(bytes, { level: 6 }));
    }
  }
}

export default defineConfig({
  plugins: [{ name: 'local-precompressed-assets', closeBundle: () => precompress('dist') }],
  server: { proxy: { '/api': 'http://127.0.0.1:8791' } },
  preview: { proxy: { '/api': 'http://127.0.0.1:8791' } },
  build: { chunkSizeWarningLimit: 1800 },
});
