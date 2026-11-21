import {
  createSyncRangeReader,
  type SnapshotTransport,
  type SyncRangeResponse,
} from '../../snapshot-source/httpSource'
import type { SnapshotSourceLocation } from '../../snapshot-source/sourceLocation'
import {
  SESSION_COOKIE,
  type StorageHost,
  type StorageOrigins,
  type StorageRequest,
  type StorageResponse,
} from './storageProfiles'

// Emulates what Chromium does around a request, as measured by the Playwright spec: CORS
// preflights for non-safelisted headers, the response CORS check, exposed headers only, and
// redirects that keep Range but drop Authorization when they leave the origin.

const SAFELISTED_RESPONSE_HEADERS = new Set([
  'cache-control',
  'content-language',
  'content-length',
  'content-type',
  'expires',
  'last-modified',
  'pragma',
])
const MAX_REDIRECTS = 5

export type Serve = (request: StorageRequest) => StorageResponse | null

interface Sent {
  status: number
  url: string
  redirected: boolean
  headers: Headers
  body: Uint8Array
  dropAfter: number | null
}

class EmulatedNetworkError extends TypeError {
  constructor(reason: string) {
    super(`Failed to fetch: ${reason}`)
  }
}

function isSafelistedRequestHeader(name: string, value: string): boolean {
  return name === 'range' && /^bytes=\d+-\d*$/.test(value)
}

export function browserLikeTransport(serve: Serve, origins: StorageOrigins) {
  const hostOf = (url: URL): StorageHost | null =>
    url.origin === origins.page ? 'page' : url.origin === origins.storage ? 'storage' : null

  function exchange(url: URL, headers: Record<string, string>, method = 'GET'): StorageResponse {
    const host = hostOf(url)
    const response = host && serve({ host, method, target: url.pathname + url.search, headers })
    if (!response) throw new EmulatedNetworkError(`no server at ${url.origin}`)
    return response
  }

  function passesCors(response: StorageResponse, credentials: boolean): boolean {
    const allowOrigin = response.headers['Access-Control-Allow-Origin']
    if (credentials) {
      return (
        allowOrigin === origins.page &&
        response.headers['Access-Control-Allow-Credentials'] === 'true'
      )
    }
    return allowOrigin === origins.page || allowOrigin === '*'
  }

  // Chromium caches a preflight per URL and header set for Access-Control-Max-Age seconds
  // (5 without one); time does not pass here, so only a Max-Age of 0 makes no entry.
  const preflightCache = new Set<string>()

  function preflight(url: URL, names: string[]): void {
    const key = `${url.href} ${names.join(',')}`
    if (preflightCache.has(key)) return
    const response = exchange(
      url,
      {
        origin: origins.page,
        'access-control-request-method': 'GET',
        'access-control-request-headers': names.join(','),
      },
      'OPTIONS',
    )
    const allowed = (response.headers['Access-Control-Allow-Headers'] ?? '')
      .split(',')
      .map((name) => name.trim().toLowerCase())
    if (!passesCors(response, false) || names.some((name) => !allowed.includes(name))) {
      throw new EmulatedNetworkError(`preflight of ${url.href} refused ${names.join(',')}`)
    }
    if (Number(response.headers['Access-Control-Max-Age'] ?? 5) > 0) preflightCache.add(key)
  }

  function send(location: SnapshotSourceLocation, requestHeaders: Record<string, string>): Sent {
    let url = new URL(location.url, origins.page)
    let headers = Object.fromEntries(
      Object.entries(requestHeaders).map(([name, value]) => [name.toLowerCase(), value]),
    )
    const withCredentials = location.credentials === 'include'
    let redirected = false
    for (let hop = 0; hop <= MAX_REDIRECTS; hop++) {
      const crossOrigin = url.origin !== origins.page
      const nonSimple = Object.entries(headers)
        .filter(([name, value]) => !isSafelistedRequestHeader(name, value))
        .map(([name]) => name)
      if (crossOrigin && nonSimple.length) preflight(url, nonSimple.sort())
      const sendCookie = crossOrigin ? withCredentials : location.credentials !== 'omit'
      const response = exchange(url, {
        ...headers,
        ...(crossOrigin ? { origin: origins.page } : {}),
        ...(sendCookie ? { cookie: SESSION_COOKIE } : {}),
      })
      if (crossOrigin && !passesCors(response, withCredentials)) {
        throw new EmulatedNetworkError(`CORS check of ${url.href} failed`)
      }
      const redirectTo = response.headers.Location
      if (response.status >= 300 && response.status < 400 && redirectTo) {
        const next = new URL(redirectTo, url)
        if (next.origin !== url.origin) delete headers.authorization
        url = next
        headers = { ...headers }
        redirected = true
        continue
      }
      return {
        status: response.status,
        url: url.href,
        redirected,
        headers: visibleHeaders(response, crossOrigin),
        body: response.body,
        dropAfter: response.dropAfter ?? null,
      }
    }
    throw new EmulatedNetworkError('too many redirects')
  }

  const fetchLike: typeof fetch = async (input, init) => {
    const signal = init?.signal
    signal?.throwIfAborted()
    const location: SnapshotSourceLocation = {
      url: String(input),
      ...(init?.credentials ? { credentials: init.credentials } : {}),
    }
    const sent = send(location, Object.fromEntries(new Headers(init?.headers).entries()))
    const response = new Response(streamOf(sent), { status: sent.status, headers: sent.headers })
    Object.defineProperty(response, 'url', { value: sent.url })
    Object.defineProperty(response, 'redirected', { value: sent.redirected })
    return response
  }

  const sendSync = (
    location: SnapshotSourceLocation,
    headers: Record<string, string>,
  ): SyncRangeResponse => {
    // A failed sync XHR names the URL, signature included, as Chromium does (measured).
    const networkError = () =>
      new DOMException(
        `Failed to execute 'send' on 'XMLHttpRequest': Failed to load '${location.url}'.`,
        'NetworkError',
      )
    let sent: Sent
    try {
      sent = send(location, headers)
    } catch (error) {
      if (error instanceof EmulatedNetworkError) throw networkError()
      throw error
    }
    if (sent.dropAfter !== null) throw networkError()
    return {
      status: sent.status,
      url: sent.url,
      contentRange: sent.headers.get('Content-Range'),
      contentType: sent.headers.get('Content-Type'),
      body: sent.body.slice(),
    }
  }

  const transport: SnapshotTransport = {
    fetch: fetchLike,
    readRangeSync: createSyncRangeReader(sendSync),
  }
  return transport
}

function visibleHeaders(response: StorageResponse, crossOrigin: boolean): Headers {
  const exposed = new Set(
    (response.headers['Access-Control-Expose-Headers'] ?? '')
      .split(',')
      .map((name) => name.trim().toLowerCase()),
  )
  const headers = new Headers()
  for (const [name, value] of Object.entries(response.headers)) {
    const lower = name.toLowerCase()
    if (!crossOrigin || SAFELISTED_RESPONSE_HEADERS.has(lower) || exposed.has(lower)) {
      headers.set(name, value)
    }
  }
  return headers
}

function streamOf(sent: Sent): ReadableStream<Uint8Array> {
  const { body, dropAfter } = sent
  let delivered = false
  return new ReadableStream<Uint8Array>({
    pull(controller) {
      if (delivered) {
        if (dropAfter === null) controller.close()
        else controller.error(new EmulatedNetworkError('connection dropped'))
        return
      }
      delivered = true
      controller.enqueue(body.slice(0, dropAfter ?? body.length))
    },
  })
}
