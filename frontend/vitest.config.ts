/// <reference types="vitest" />

import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'
import path from 'path'
import type { PluginOption } from 'vite'

export default defineConfig({
  plugins: [vue() as PluginOption],

  resolve: {
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },

test: {
  globals: true,
  environment: 'jsdom',
  setupFiles: './tests/setup.ts',
  include: ['src/**/*.{test,spec}.{ts,tsx}'],
  exclude: ['**/node_modules/**', 'tests/integration/**'],
    server: {
      deps: {
        // @fnnx-ai/common ships ESM with extensionless relative imports
        // (e.g. import ... from './ndarray'), which Node's native ESM resolver
        // rejects. Inlining lets Vite transform and resolve them.
        inline: [/@fnnx-ai\/common/, /@fnnx-ai\/web/],
      },
    },
  coverage: {
    provider: 'v8',
    reportsDirectory: 'coverage',
  },
},
})
