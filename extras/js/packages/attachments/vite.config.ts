import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'
import dts from 'vite-plugin-dts'
import { dependencies, peerDependencies } from './package.json'

const peers = Object.keys({ ...peerDependencies, ...dependencies })

// Keep npm imports external in the ESM distribution. In the script-tag
// distribution, bundle readers without a browser global alongside the preview.
const bundledForBrowser = new Set([
  'hyparquet',
  'hyparquet-compressors',
  ...Object.keys(dependencies),
])

export default defineConfig(({ mode }) => {
  const browser = mode === 'browser-global'
  const external = browser ? peers.filter((peer) => !bundledForBrowser.has(peer)) : peers
  return {
    plugins: [
      vue(),
      vueDevTools(),
      !browser &&
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
      emptyOutDir: !browser,
      sourcemap: !!process.env.LUML_BUILD_SOURCEMAP,
      lib: {
        formats: [browser ? 'umd' : 'es'],
        entry: fileURLToPath(new URL('./src/index.ts', import.meta.url)),
        name: 'luml-attachments',
        fileName: (format) => `luml-attachments.${format}.js`,
      },
      rollupOptions: {
        external: (id) =>
          !id.endsWith('.css') && external.some((peer) => id === peer || id.startsWith(`${peer}/`)),
        output: {
          globals: {
            '@codemirror/view': 'view',
            vue: 'Vue',
            primevue: 'PrimeVue',
            pinia: 'Pinia',
            'lucide-vue-next': 'LucideVueNext',
            arquero: 'aq',
            'apache-arrow': 'Arrow',
            'js-yaml': 'jsyaml',
            dompurify: 'DOMPurify',
            marked: 'marked',
          },
        },
      },
    },
  }
})
