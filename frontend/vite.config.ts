import { fileURLToPath, URL } from 'node:url'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

export default defineConfig(({ mode }) => ({
  plugins: [vue(), vueDevTools()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  optimizeDeps: {
    exclude: ['onnxruntime-web'],
  },
  server: {
    headers: {
      'Cross-Origin-Opener-Policy': 'same-origin',
      'Cross-Origin-Embedder-Policy': 'require-corp',
    },
    // Lets the dev server be reached through an ngrok tunnel.
    allowedHosts: ['.ngrok-free.app'],
    ...(mode === 'development' && {
      proxy: {
        // Same-origin API when VITE_API_URL is empty: one tunnel serves both
        // the app and the backend, no CORS and no ngrok interstitial on XHR.
        '/v1': {
          target: 'http://127.0.0.1:8000',
          changeOrigin: true,
        },
        '/jupyter': {
          target: 'http://localhost:8000',
          changeOrigin: true,
          rewrite: (path) => path.replace(/^\/jupyter/, ''),
        },
      },
    }),
  },
  worker: {
    format: 'es',
  },
}))
