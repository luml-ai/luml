import type { AsyncBuffer } from 'hyparquet'

const sources = new Map<string, AsyncBuffer>()
const connections = new Map<string, Promise<string>>()

// Keep authenticated URLs and headers on the page. The worker can ask only for
// slices of a source registered here, even after the browser restarts it.
async function servePreviewBytes(event: MessageEvent) {
  if (event.source !== navigator.serviceWorker.controller) return
  const { type, url, start, end } = event.data ?? {}
  const port = event.ports[0]
  if (type !== 'attachment-preview-read' || !port) return
  const source = sources.get(url)
  if (!source) {
    port.postMessage({ error: 'Preview closed' })
    return
  }
  if (start === undefined && end === undefined) {
    port.postMessage({ size: source.byteLength })
    return
  }
  if (
    !Number.isSafeInteger(start) ||
    !Number.isSafeInteger(end) ||
    start < 0 ||
    end <= start ||
    end > source.byteLength
  ) {
    port.postMessage({ error: 'Invalid byte range' })
    return
  }
  try {
    const buffer = await source.slice(start, end)
    if (buffer.byteLength !== end - start) throw new Error('Incomplete preview data')
    port.postMessage({ buffer })
  } catch {
    port.postMessage({ error: 'Could not read preview data' })
  }
}

async function connect(workerUrl: string): Promise<string> {
  const workers = navigator.serviceWorker
  if (!workers) throw new Error('Streaming previews require a secure browser connection')
  workers.addEventListener('message', servePreviewBytes)
  await workers.register(workerUrl)
  return new Promise((resolve, reject) => {
    const channel = new MessageChannel()
    const cleanup = () => {
      clearTimeout(timer)
      workers.removeEventListener('controllerchange', identify)
      channel.port1.close()
    }
    function identify() {
      if (workers.controller?.scriptURL !== workerUrl) return
      workers.removeEventListener('controllerchange', identify)
      workers.controller.postMessage({ type: 'attachment-preview-connect' }, [channel.port2])
    }
    const timer = setTimeout(() => {
      cleanup()
      reject(new Error('Could not connect to the preview service worker'))
    }, 15_000)
    channel.port1.onmessage = ({ data }) => {
      cleanup()
      if (typeof data.clientId === 'string') resolve(data.clientId)
      else reject(new Error('Could not identify the preview client'))
    }
    workers.addEventListener('controllerchange', identify)
    identify()
  })
}

export async function createPreviewStreamUrl(
  fileName: string,
  source: AsyncBuffer,
  workerUrl: string,
): Promise<string> {
  const extension = /\.([a-z0-9]+)$/i.exec(fileName)?.[1]?.toLowerCase()
  if (!extension || !Number.isSafeInteger(source.byteLength) || source.byteLength < 0) {
    throw new Error('Invalid streaming preview source')
  }
  const absoluteUrl = new URL(workerUrl, document.baseURI).href
  let connection = connections.get(absoluteUrl)
  if (!connection) {
    connection = connect(absoluteUrl).catch((error) => {
      connections.delete(absoluteUrl)
      throw error
    })
    connections.set(absoluteUrl, connection)
  }
  const clientId = await connection
  const url = new URL(
    `./__attachment_preview__/${clientId}/${crypto.randomUUID()}.${extension}`,
    absoluteUrl,
  ).href
  sources.set(url, source)
  return url
}

export function releasePreviewStreamUrl(url: string) {
  sources.delete(url)
}
