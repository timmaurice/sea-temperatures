import { defineConfig } from 'vitest/config';

export default defineConfig({
  test: {
    environment: 'jsdom',
    // The Playwright suite lives under test/e2e and drives a real browser
    // against a real Home Assistant. Vitest would otherwise pick the .spec.ts
    // files up by its default glob and fail on the Playwright imports.
    exclude: ['**/node_modules/**', '**/dist/**', 'test/e2e/**'],
    globals: true,
    setupFiles: './frontend/test/setup.ts',
    alias: { '\\.scss$': './frontend/test/styleMock.ts' },
  },
});
