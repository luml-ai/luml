/// <reference types="vitest/config" />
import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vitest/config'
import vue from '@vitejs/plugin-vue'

// The kit serves the built bundle from its monitoring dashboard under /monitoring/app.
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
    outDir: fileURLToPath(
      new URL('../kit/luml_satellite/monitoring/dashboard/static', import.meta.url),
    ),
    emptyOutDir: true,
    // A single inlined bundle carrying ApexCharts is expectedly over the default 500 kB hint.
    chunkSizeWarningLimit: 1500,
    rollupOptions: {
      // Committed bundle: one stable app.js (dynamic imports inlined so ApexCharts is not
      // a hash-named chunk), one stylesheet, index.html.
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
