import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import dts from 'vite-plugin-dts'
import { peerDependencies } from './package.json'

const peers = Object.keys(peerDependencies)

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
    sourcemap: !!process.env.LUML_BUILD_SOURCEMAP,
    lib: {
      entry: fileURLToPath(new URL('./src/index.ts', import.meta.url)),
      name: 'luml-experiments',
      fileName: (format) => `luml-experiments.${format}.js`,
    },
    rollupOptions: {
      // extract peer CSS into the stylesheet so the JS entry stays worker-safe
      external: (id) =>
        !id.endsWith('.css') && peers.some((peer) => id === peer || id.startsWith(`${peer}/`)),
      output: {
        globals: {
          vue: 'Vue',
          primevue: 'PrimeVue',
          pinia: 'Pinia',
          'lucide-vue-next': 'LucideVueNext',
          arquero: 'aq',
          dompurify: 'DOMPurify',
          marked: 'marked',
          '@vueuse/core': 'VueUse',
          'js-yaml': 'jsyaml',
          jszip: 'JSZip',
          'sql.js': 'initSqlJs',
          uuid: 'uuid',
          'plotly.js-dist': 'Plotly',
        },
      },
    },
  },
  // root: fileURLToPath(new URL('./src/demo', import.meta.url)),
})
