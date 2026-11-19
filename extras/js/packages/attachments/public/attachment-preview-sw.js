// A browser's media reader uses ordinary GET, HEAD, and Range requests. Keep
// sources on the originating page so worker restarts and multiple tabs are safe.
const prefix = new URL('__attachment_preview__/', self.registration.scope).href
const mediaTypes = {
  mp3: 'audio/mpeg',
  wav: 'audio/wav',
  ogg: 'audio/ogg',
  mp4: 'video/mp4',
  webm: 'video/webm',
  ogv: 'video/ogg',
  pdf: 'application/pdf',
}

self.addEventListener('install', (event) => event.waitUntil(self.skipWaiting()))
self.addEventListener('activate', (event) => event.waitUntil(self.clients.claim()))
self.addEventListener('message', (event) => {
  if (event.data?.type === 'attachment-preview-connect') {
    event.ports[0]?.postMessage({ clientId: event.source.id })
  }
})

function askClient(client, url, range = {}) {
  return new Promise((resolve, reject) => {
    const channel = new MessageChannel()
    const timer = setTimeout(() => {
      channel.port1.close()
      reject(new Error('Preview client did not respond'))
    }, 60_000)
    channel.port1.onmessage = ({ data }) => {
      clearTimeout(timer)
      channel.port1.close()
      if (data.error) reject(new Error(data.error))
      else resolve(data)
    }
    client.postMessage({ type: 'attachment-preview-read', url, ...range }, [channel.port2])
  })
}

function parseRange(header, size) {
  if (header === null) return [0, size]
  const match = /^bytes=(\d*)-(\d*)$/i.exec(header)
  if (!match || !(match[1] || match[2]) || !size) return null
  const first = Number(match[1])
  const last = Number(match[2])
  if (!Number.isSafeInteger(first) || !Number.isSafeInteger(last)) return null
  if (!match[1]) return last > 0 ? [Math.max(0, size - last), size] : null
  const end = match[2] ? Math.min(last, size - 1) + 1 : size
  return first < end ? [first, end] : null
}

async function serve(request) {
  const [owner, name] = request.url.slice(prefix.length).split('/')
  const type = mediaTypes[name?.split('.').pop()]
  if (typeof type !== 'string') return new Response(null, { status: 404 })
  if (!['GET', 'HEAD'].includes(request.method)) {
    return new Response(null, { status: 405, headers: { Allow: 'GET, HEAD' } })
  }
  const client = await self.clients.get(owner)
  if (!client) return new Response(null, { status: 410 })
  const { size } = await askClient(client, request.url)
  const header = request.headers.get('Range')
  const range = parseRange(header, size)
  if (!range) {
    return new Response(null, { status: 416, headers: { 'Content-Range': `bytes */${size}` } })
  }
  const [start, end] = range
  const headers = new Headers({
    'Accept-Ranges': 'bytes',
    'Content-Length': String(end - start),
    'Content-Type': type,
    'X-Content-Type-Options': 'nosniff',
    'Cache-Control': 'no-store',
  })
  if (header) headers.set('Content-Range', `bytes ${start}-${end - 1}/${size}`)
  const init = { status: header ? 206 : 200, headers }
  if (request.method === 'HEAD' || !size) return new Response(null, init)

  let position = start
  const body = new ReadableStream({
    async pull(controller) {
      const next = Math.min(position + 1024 * 1024, end)
      const { buffer } = await askClient(client, request.url, { start: position, end: next })
      controller.enqueue(new Uint8Array(buffer))
      position = next
      if (position === end) controller.close()
    },
  })
  return new Response(body, init)
}

self.addEventListener('fetch', (event) => {
  if (event.request.url.startsWith(prefix)) {
    event.respondWith(serve(event.request).catch(() => new Response(null, { status: 410 })))
  }
})
