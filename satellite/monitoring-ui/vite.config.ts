/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// The Agent serves the built bundle from agent/monitoring/static under /monitoring/app.
// base './' keeps asset URLs relative so they resolve under that sub-path inside the iframe.
export default defineConfig({
  base: './',
  plugins: [vue()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // Dev only: proxy the Query API to a locally running Agent so `npm run dev` works.
    proxy: {
      '/monitoring/api': { target: 'http://localhost:8000', changeOrigin: true },
    },
  },
  build: {
    outDir: fileURLToPath(new URL('../agent/monitoring/static', import.meta.url)),
    emptyOutDir: true,
    // A single inlined bundle carrying ApexCharts is expectedly over the default 500 kB hint.
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      // The bundle is committed and served with the Agent, so keep the output to a
      // single stable set of files: one app.js (dynamic imports inlined so ApexCharts
      // is not split into a hash-named chunk), one stylesheet, and index.html.
      output: {
        inlineDynamicImports: true,
        entryFileNames: 'assets/app.js',
        assetFileNames: 'assets/app[extname]',
      },
    },
  },
  test: {
    globals: true,
    environment: 'jsdom',
    include: ['src/**/*.{test,spec}.ts'],
  },
})
