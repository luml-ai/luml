import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import tailwindcss from '@tailwindcss/vite'

const appSrc = fileURLToPath(new URL('./src', import.meta.url))
const experimentsSrc = fileURLToPath(
  new URL('../../extras/js/packages/experiments/src', import.meta.url),
)
const attachmentsSrc = fileURLToPath(
  new URL('../../extras/js/packages/attachments/src', import.meta.url),
)

export default defineConfig(({ mode }) => ({
  plugins: [vue(), tailwindcss()],
  resolve: {
    alias: {
      '@luml/experiments': fileURLToPath(
        new URL('../../extras/js/packages/experiments/src/index.ts', import.meta.url),
      ),
      '@luml/attachments': fileURLToPath(
        new URL('../../extras/js/packages/attachments/src/index.ts', import.meta.url),
      ),
      '@experiments': experimentsSrc,
      '@attachments': attachmentsSrc,
      '@': appSrc,
    },
  },
  server: {
    port: 5173,
    ...(mode === 'development' && {
      proxy: {
        '/api': {
          target: 'http://localhost:5000',
          changeOrigin: true,
        },
      },
    }),
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
}))
