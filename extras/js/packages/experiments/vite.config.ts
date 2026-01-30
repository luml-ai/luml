import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import dts from 'vite-plugin-dts'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
    dts({
      entryRoot: 'src',
      outDir: 'dist',
      tsconfigPath: './tsconfig.build.json',
    }),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  build: {
    lib: {
      entry: fileURLToPath(new URL('./src/index.ts', import.meta.url)),
      name: 'luml-experiments',
      fileName: (format) => `luml-experiments.${format}.js`,
    },
    rollupOptions: {
      external: ['vue', 'plotly.js-dist', 'primevue', 'pinia'],
      output: {
        globals: {
          vue: 'Vue',
          'plotly.js-dist': 'Plotly',
        },
      },
    },
  },
  // root: fileURLToPath(new URL('./src/demo', import.meta.url)),
})
