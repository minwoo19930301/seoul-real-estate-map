import { defineConfig } from '@playwright/test';

export default defineConfig({
  testDir: './tests', testMatch: '**/*.spec.ts', timeout: 45_000, workers: 1,
  use: { baseURL: 'http://127.0.0.1:4173', channel: 'chrome', viewport: { width: 1440, height: 960 }, screenshot: 'only-on-failure', trace: 'retain-on-failure' },
  reporter: [['list']],
});
