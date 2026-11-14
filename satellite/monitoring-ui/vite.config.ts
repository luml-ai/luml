import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig(({ mode }) => ({
  base: './',
  plugins: [vue(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    ...(mode === 'development' && {
      proxy: {
        '/monitoring/api': {
          target: 'http://localhost:8000',
          changeOrigin: true,
        },
      },
    }),
  },
  build: {
    chunkSizeWarningLimit: 1500,
  },
}))
