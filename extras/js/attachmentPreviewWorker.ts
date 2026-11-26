import { readFileSync } from 'node:fs'
import type { Plugin } from 'vite'

const name = 'attachment-preview-sw.js'
const source = new URL(`./packages/attachments/public/${name}`, import.meta.url)

// A service worker's script directory determines which pages it can control.
// Serve it at the app root in development and emit the same file in production.
export function attachmentPreviewWorker(): Plugin {
  return {
    name: 'attachment-preview-worker',
    configureServer(server) {
      server.middlewares.use(`${server.config.base}${name}`, (_request, response) => {
        response.setHeader('Content-Type', 'text/javascript')
        response.end(readFileSync(source))
      })
    },
    generateBundle() {
      this.emitFile({ type: 'asset', fileName: name, source: readFileSync(source) })
    },
  }
}
