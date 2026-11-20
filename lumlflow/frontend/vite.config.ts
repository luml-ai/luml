import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import { attachmentPreviewWorker } from '../../extras/js/attachmentPreviewWorker'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig(({ mode }) => ({
  plugins: [attachmentPreviewWorker(), vue(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
    dedupe: ['vue', 'pinia'],
  },
  server: {
    port: 5173,
    ...(mode === 'development' && {
      proxy: {
        '/api': {
          // 127.0.0.1 rather than localhost: on macOS the latter resolves to
          // ::1 first, where AirPlay Receiver answers port 5000 with a 403.
          target: 'http://127.0.0.1:5000',
          changeOrigin: true,
          ws: true,
        },
      },
    }),
  },
  worker: { format: 'es' },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
  },
}))
