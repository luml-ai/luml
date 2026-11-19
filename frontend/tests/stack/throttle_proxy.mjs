// A delaying HTTP proxy for the stack suites: browser -> proxy -> storage (or Flow). It sits on
// the real network path, so it slows every request the page and its Web Worker make, whatever
// API they use (sync XHR included), and it logs what it served so the specs can measure it.
//
//   node throttle_proxy.mjs <listen port> <target port> [port file]
//
// Listen port 0 binds a free port; the bound port is written to the port file once it listens.
//
// Controlled over the same port under /__e2e/ (the specs call it from Node):
//   POST /__e2e/config  {latencyMs, bytesPerSecond, throttleMatching, stallMatching, stripRange,
//                        refuseSeen, refuseMatching, refuseOverlapping, failMatching,
//                        storageFailure}
//   POST /__e2e/release the held requests answered; later matching ones are held still
//   GET  /__e2e/log     the requests served since the last reset
//   POST /__e2e/reset   default config, empty log, held requests answered
import { renameSync, writeFileSync } from 'node:fs'
import http from 'node:http'

const [listenPort, targetPort] = process.argv.slice(2, 4).map(Number)
const portFile = process.argv[4]
const TARGET_HOST = '127.0.0.1'
const CHUNK_BYTES = 16 * 1024

const DEFAULT_CONFIG = {
  /** Added before each request is forwarded: a round trip on a slow link. */
  latencyMs: 0,
  /** Shared by all responses at once, as one link is; 0 is unlimited. */
  bytesPerSecond: 0,
  /** A regular expression over the path; only matching requests are slowed. Null is all. */
  throttleMatching: null,
  /**
   * A regular expression over `<path>?<query> <range>`: matching requests are held until it is
   * cleared (then answered as usual) or the client gives up.
   */
  stallMatching: null,
  /**
   * Forward without the Range header, as storage that ignores Range answers. The answers are
   * marked `no-store`: Chrome would otherwise answer later Range reads from the cached whole
   * object, and the viewer would never see the storage ignore Range.
   */
  stripRange: false,
  /**
   * Sends every request signed with a signature seen before this was set with that signature
   * corrupted, so the storage itself refuses it: a URL that stopped working mid-session.
   */
  refuseSeen: false,
  /**
   * A regular expression over the path: every matching signed request is sent with its
   * signature corrupted, so the storage refuses it, until this is cleared.
   */
  refuseMatching: null,
  /** `[first, last]`: refuseMatching only refuses Range reads that overlap these bytes. */
  refuseOverlapping: null,
  /**
   * A regular expression over `<path>?<query>`: matching requests are answered 500 without
   * being forwarded, until this is cleared. For servers whose requests are not signed (Flow).
   */
  failMatching: null,
  /**
   * `{matching, status, times}`: GET requests whose `<path>?<query> <range>` match are
   * answered with `status` (and the CORS headers a cross-origin page needs to see it), `times`
   * times or, with null, until this is cleared. Storage that fails for a while.
   */
  storageFailure: null,
}

let config = { ...DEFAULT_CONFIG }
let log = []
let seenSignatures = new Set()
let refusedSignatures = new Set()
let held = new Set()
// The bandwidth cap is a single clock: the time the link is busy until.
let linkBusyUntil = 0

const sleep = (ms) => new Promise((resolve) => setTimeout(resolve, ms))

function signatureParam(url) {
  for (const name of ['X-Amz-Signature', 'sig']) {
    if (url.searchParams.has(name)) return name
  }
  return null
}

function refused(url, range) {
  if (!config.refuseMatching || !new RegExp(config.refuseMatching).test(url.pathname)) return false
  if (!config.refuseOverlapping) return true
  const [first, last] = config.refuseOverlapping
  const bytes = range ? /^bytes=(\d+)-(\d+)$/.exec(range) : null
  return bytes !== null && Number(bytes[1]) <= last && Number(bytes[2]) >= first
}

async function paced(chunk, throttled) {
  if (!throttled || !config.bytesPerSecond) return
  const now = Date.now()
  linkBusyUntil = Math.max(linkBusyUntil, now) + (chunk.length / config.bytesPerSecond) * 1000
  if (linkBusyUntil > now) await sleep(linkBusyUntil - now)
}

function readJson(request) {
  return new Promise((resolve, reject) => {
    let body = ''
    request.on('data', (part) => (body += part))
    request.on('end', () => {
      try {
        resolve(body ? JSON.parse(body) : {})
      } catch (error) {
        reject(error)
      }
    })
  })
}

function releaseHeld() {
  for (const release of held) release()
  held = new Set()
}

async function control(request, response, path) {
  if (path === '/__e2e/config' && request.method === 'POST') {
    config = { ...config, ...(await readJson(request)) }
    if (config.refuseSeen) refusedSignatures = new Set(seenSignatures)
    if (!config.stallMatching) releaseHeld()
  } else if (path === '/__e2e/release' && request.method === 'POST') {
    releaseHeld()
  } else if (path === '/__e2e/reset' && request.method === 'POST') {
    config = { ...DEFAULT_CONFIG }
    log = []
    refusedSignatures = new Set()
    releaseHeld()
  } else if (path === '/__e2e/log' && request.method === 'GET') {
    response.writeHead(200, { 'content-type': 'application/json' })
    response.end(JSON.stringify(log))
    return
  } else {
    response.writeHead(404)
    response.end()
    return
  }
  response.writeHead(200, { 'content-type': 'application/json' })
  response.end(JSON.stringify(config))
}

async function forward(request, response) {
  const url = new URL(request.url, `http://${TARGET_HOST}`)
  const range = request.headers['range'] ?? null
  const entry = {
    method: request.method,
    path: url.pathname,
    range,
    status: 0,
    bytes: 0,
    stalled: false,
    startedAt: Date.now(),
    firstByteAt: 0,
    endedAt: 0,
  }
  log.push(entry)

  const signature = signatureParam(url)
  if (signature) {
    const value = url.searchParams.get(signature)
    const refuse = request.method !== 'OPTIONS' && refused(url, range)
    if (refuse || refusedSignatures.has(value)) url.searchParams.set(signature, `${value}x`)
    else seenSignatures.add(value)
  }
  const fail = config.failMatching && new RegExp(config.failMatching)
  if (fail && request.method !== 'OPTIONS' && fail.test(`${url.pathname}${url.search}`)) {
    entry.status = 500
    response.writeHead(500, { 'content-type': 'application/json' })
    response.end(JSON.stringify({ detail: 'Failed on purpose by the test proxy' }))
    entry.endedAt = Date.now()
    return
  }
  const failure = config.storageFailure
  if (
    failure &&
    request.method === 'GET' &&
    failure.times !== 0 &&
    new RegExp(failure.matching).test(`${url.pathname}${url.search} ${range}`)
  ) {
    if (failure.times !== null) failure.times -= 1
    entry.status = failure.status
    response.writeHead(failure.status, {
      'content-type': 'text/plain',
      'access-control-allow-origin': request.headers.origin ?? '*',
      'cross-origin-resource-policy': 'cross-origin',
    })
    response.end('Failed on purpose by the test proxy')
    entry.endedAt = Date.now()
    return
  }
  const stall = config.stallMatching && new RegExp(config.stallMatching)
  if (
    stall &&
    request.method !== 'OPTIONS' &&
    stall.test(`${url.pathname}${url.search} ${range}`)
  ) {
    entry.stalled = true
    await new Promise((resolve) => {
      held.add(resolve)
      request.socket.on('close', resolve)
    })
    if (request.socket.destroyed) {
      entry.endedAt = Date.now()
      return
    }
  }
  const throttled =
    !config.throttleMatching || new RegExp(config.throttleMatching).test(url.pathname)
  if (throttled && config.latencyMs) await sleep(config.latencyMs)

  const headers = { ...request.headers }
  if (config.stripRange) delete headers['range']
  const upstream = http.request(
    {
      host: TARGET_HOST,
      port: targetPort,
      method: request.method,
      path: `${url.pathname}${url.search}`,
      headers,
    },
    async (answer) => {
      entry.status = answer.statusCode ?? 0
      const answerHeaders = config.stripRange
        ? { ...answer.headers, 'cache-control': 'no-store' }
        : answer.headers
      response.writeHead(entry.status, answerHeaders)
      entry.firstByteAt = Date.now()
      try {
        for await (const chunk of answer) {
          for (let start = 0; start < chunk.length; start += CHUNK_BYTES) {
            const part = chunk.subarray(start, start + CHUNK_BYTES)
            await paced(part, throttled)
            if (response.destroyed) throw new Error('client went away')
            response.write(part)
            entry.bytes += part.length
          }
        }
        response.end()
      } catch {
        answer.destroy()
        response.destroy()
      }
      entry.endedAt = Date.now()
    },
  )
  upstream.on('error', () => {
    entry.status = 502
    entry.endedAt = Date.now()
    if (!response.headersSent) response.writeHead(502)
    response.end()
  })
  request.pipe(upstream)
}

const server = http.createServer((request, response) => {
  const path = request.url?.split('?')[0] ?? '/'
  const handle = path.startsWith('/__e2e/') ? control : forward
  handle(request, response, path).catch(() => {
    if (!response.headersSent) response.writeHead(500)
    response.end()
  })
})
server.keepAliveTimeout = 60_000
server.listen(listenPort, '127.0.0.1', () => {
  if (!portFile) return
  // Renamed into place, so a reader never sees a partly written port.
  writeFileSync(`${portFile}.tmp`, String(server.address().port))
  renameSync(`${portFile}.tmp`, portFile)
})
