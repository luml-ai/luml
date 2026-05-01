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
    coverage: {
      provider: 'v8',
      reportsDirectory: 'coverage',
    },
  },
})
