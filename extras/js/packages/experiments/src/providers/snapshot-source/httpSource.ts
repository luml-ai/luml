import { RangeChunkCache, type RangeCacheOptions } from './RangeChunkCache'
import type { RangeFile } from './RangeSqliteEngine'
import {
  errorName,
  SnapshotFormatError,
  SnapshotRangeUnsupportedError,
  SnapshotSourceExpiredError,
  SnapshotSourcePageError,
  SnapshotSourceRedirectError,
  SnapshotSourceTimeoutError,
  SnapshotSourceTooLargeError,
} from './errors'
import { SQLITE_HEADER_SIZE } from './sqliteHeader'
import {
  redirectDroppedHeaders,
  toSourceLocation,
  type SnapshotSourceLocation,
  type SnapshotSourceRef,
} from './sourceLocation'

export type SyncReadRange = (
  location: SnapshotSourceLocation,
  offset: number,
  length: number,
) => Uint8Array

export interface SnapshotTransport {
  fetch: typeof fetch
  readRangeSync: SyncReadRange
}

/** What a synchronous GET returned; `url` is the final URL after redirects. */
export interface SyncRangeResponse {
  status: number
  url: string
  /** Null when absent or not exposed across origins. */
  contentRange: string | null
  /** Always exposed across origins (a CORS-safelisted response header); null when absent. */
  contentType?: string | null
  body: Uint8Array
}

export type SyncSend = (
  location: SnapshotSourceLocation,
  headers: Record<string, string>,
) => SyncRangeResponse

/** `header`: the bytes the probe read from the member's start. */
export type HeaderProbe = { rangeIgnored: true } | { rangeIgnored: false; header: Uint8Array }

function rangeHeader(offset: number, length: number): string {
  return `bytes=${offset}-${offset + length - 1}`
}

function requestHeaders(location: SnapshotSourceLocation, range?: string): Record<string, string> {
  return range ? { ...location.headers, Range: range } : { ...location.headers }
}

function isAbortError(error: unknown): boolean {
  return error instanceof DOMException && error.name === 'AbortError'
}

// Messages of the errors below never carry a URL, header value or response text: they travel
// to the UI, and presigned URLs hold their signature in the query.

/** The server answered a Range request, but not with the requested range. */
export class RangeNotHonouredError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'RangeNotHonouredError'
  }
}

/** A request with storage headers failed after a redirect to another origin. */
export class RedirectDroppedHeadersError extends Error {
  constructor(message: string) {
    super(message)
    this.name = 'RedirectDroppedHeadersError'
  }
}

/** A Range request answered with a status outside 2xx. */
export class RangeStatusError extends Error {
  constructor(readonly status: number) {
    super(`Range request returned status ${status}`)
    this.name = 'RangeStatusError'
  }
}

/** A Range request answered 2xx with a web page (a sign-in page) instead of the bytes. */
export class RangePageAnswerError extends Error {
  constructor() {
    super('Range request was answered with a web page')
    this.name = 'RangePageAnswerError'
  }
}

function isPage(contentType: string | null | undefined): boolean {
  return /^\s*(text\/html|application\/xhtml\+xml)\b/i.test(contentType ?? '')
}

/**
 * Checks a 206 response's `Content-Range` against the request. Cross-origin responses expose
 * the header only when the storage lists it in `Access-Control-Expose-Headers`, so a missing
 * header is accepted.
 */
function checkContentRange(contentRange: string | null, offset: number, length: number): void {
  if (contentRange === null) return
  const match = /^bytes (\d+)-(\d+)\//.exec(contentRange.trim())
  if (match && Number(match[1]) === offset && Number(match[2]) === offset + length - 1) return
  throw new RangeNotHonouredError(`Content-Range does not match ${rangeHeader(offset, length)}`)
}

function responseHeaderOf(request: XMLHttpRequest, name: string): string | null {
  // getAllResponseHeaders lists only exposed headers and, unlike getResponseHeader, never logs.
  const line = new RegExp(`^${name}:(.*)$`, 'im').exec(request.getAllResponseHeaders())
  return line?.[1]?.trim() ?? null
}

/**
 * A storage that accepts the connection and never answers would block the worker thread for
 * good: nothing on the main thread can interrupt a blocked `send()`.
 */
export const SYNC_RANGE_TIMEOUT_MS = 30_000

/** Sync XHR is the only blocking HTTP API in a worker; a timeout throws a `TimeoutError`. */
export function sendSyncXhr(
  location: SnapshotSourceLocation,
  headers: Record<string, string>,
): SyncRangeResponse {
  const request = new XMLHttpRequest()
  request.open('GET', location.url, false)
  // Allowed for sync requests in workers only, which is where this runs.
  request.timeout = SYNC_RANGE_TIMEOUT_MS
  request.responseType = 'arraybuffer'
  request.withCredentials = location.credentials === 'include'
  for (const [name, value] of Object.entries(headers)) request.setRequestHeader(name, value)
  request.send()
  return {
    status: request.status,
    url: request.responseURL ?? '',
    contentRange: responseHeaderOf(request, 'content-range'),
    contentType: responseHeaderOf(request, 'content-type'),
    body: new Uint8Array((request.response as ArrayBuffer | null) ?? new ArrayBuffer(0)),
  }
}

/**
 * A synchronous Range reader over `send`. Any 2xx is returned as is (some storages honour
 * Range with status 200; the caller checks the length); a mismatching `Content-Range` throws
 * `RangeNotHonouredError`, a web page `RangePageAnswerError`, a failure behind a cross-origin
 * redirect that dropped the storage headers `RedirectDroppedHeadersError`, any other status
 * `RangeStatusError`.
 */
export function createSyncRangeReader(send: SyncSend): SyncReadRange {
  return (location, offset, length) => {
    const response = send(location, requestHeaders(location, rangeHeader(offset, length)))
    if (response.status < 200 || response.status >= 300) {
      if (redirectDroppedHeaders(location, response.url)) {
        throw new RedirectDroppedHeadersError(
          `Range request returned status ${response.status} after a redirect to another origin`,
        )
      }
      throw new RangeStatusError(response.status)
    }
    if (isPage(response.contentType)) throw new RangePageAnswerError()
    checkContentRange(response.contentRange, offset, length)
    return response.body
  }
}

const readRangeOverXhr = createSyncRangeReader(sendSyncXhr)

export function xhrReadRange(
  source: SnapshotSourceRef,
  offset: number,
  length: number,
): Uint8Array {
  return readRangeOverXhr(toSourceLocation(source), offset, length)
}

export const browserTransport: SnapshotTransport = {
  fetch: (input, init) => fetch(input, init),
  readRangeSync: xhrReadRange,
}

async function fetchOrExpire(
  transport: SnapshotTransport,
  modelId: string,
  location: SnapshotSourceLocation,
  init: { range?: string; signal?: AbortSignal },
): Promise<Response> {
  try {
    return await transport.fetch(location.url, {
      headers: requestHeaders(location, init.range),
      signal: init.signal,
      ...(location.credentials ? { credentials: location.credentials } : {}),
    })
  } catch (error) {
    if (isAbortError(error)) throw error
    throw new SnapshotSourceExpiredError(modelId, `Snapshot request failed: ${errorName(error)}`)
  }
}

async function failedResponseError(
  modelId: string,
  location: SnapshotSourceLocation,
  response: Response,
  what: string,
): Promise<Error> {
  await response.body?.cancel()
  const message = `${what} returned status ${response.status}`
  if (response.redirected && redirectDroppedHeaders(location, response.url)) {
    return new SnapshotSourceRedirectError(modelId, `${message} after a redirect to another origin`)
  }
  return new SnapshotSourceExpiredError(modelId, message)
}

/**
 * Reads the first `probeBytes` of a member (all of it when smaller), the SQLite header first;
 * reports when the server ignored the Range header. Reading a whole first chunk lets the
 * chunk cache start with the pages every open reads.
 */
export async function probeSnapshotHeader(
  transport: SnapshotTransport,
  modelId: string,
  source: SnapshotSourceRef,
  memberOffset: number,
  memberSize: number,
  probeBytes = SQLITE_HEADER_SIZE,
  signal?: AbortSignal,
): Promise<HeaderProbe> {
  if (memberSize < SQLITE_HEADER_SIZE) {
    throw new SnapshotFormatError(modelId, `member is truncated: ${memberSize} bytes`)
  }
  const location = toSourceLocation(source)
  const length = Math.min(Math.max(probeBytes, SQLITE_HEADER_SIZE), memberSize)
  const response = await fetchOrExpire(transport, modelId, location, {
    range: rangeHeader(memberOffset, length),
    signal,
  })
  if (!response.ok) {
    throw await failedResponseError(modelId, location, response, 'Snapshot header request')
  }
  await rejectPage(modelId, response)
  try {
    checkContentRange(response.headers.get('Content-Range'), memberOffset, length)
  } catch (error) {
    await response.body?.cancel()
    throw new SnapshotRangeUnsupportedError(modelId, (error as Error).message)
  }
  const header = await readAtMost(response, length)
  return header?.length === length ? { rangeIgnored: false, header } : { rangeIgnored: true }
}

/** Reads `length` bytes at `offset`; null when the storage ignored Range or sent another length. */
export async function readSourceRange(
  transport: SnapshotTransport,
  modelId: string,
  source: SnapshotSourceRef,
  offset: number,
  length: number,
  signal?: AbortSignal,
): Promise<Uint8Array | null> {
  const location = toSourceLocation(source)
  const response = await fetchOrExpire(transport, modelId, location, {
    range: rangeHeader(offset, length),
    signal,
  })
  if (!response.ok) {
    throw await failedResponseError(modelId, location, response, 'Snapshot range request')
  }
  await rejectPage(modelId, response)
  try {
    checkContentRange(response.headers.get('Content-Range'), offset, length)
  } catch (error) {
    await response.body?.cancel()
    throw error
  }
  const body = await readAtMost(response, length)
  return body?.length === length ? body : null
}

async function rejectPage(modelId: string, response: Response): Promise<void> {
  if (!isPage(response.headers.get('Content-Type'))) return
  await response.body?.cancel()
  throw new SnapshotSourcePageError(modelId)
}

/**
 * The body when it is at most `limit` bytes, else null. Some S3-compatible storages honour
 * Range with status 200, so only the body's length tells a range from a whole object; a
 * larger body is abandoned as soon as that is known instead of being downloaded.
 */
async function readAtMost(response: Response, limit: number): Promise<Uint8Array | null> {
  const declared = response.headers.get('Content-Length')
  if (declared !== null && Number(declared) > limit) {
    await response.body?.cancel()
    return null
  }
  if (!response.body) return new Uint8Array(0)
  const reader = response.body.getReader()
  const body = new Uint8Array(limit)
  let filled = 0
  for (;;) {
    const { done, value } = await reader.read()
    if (done) return body.subarray(0, filled)
    if (filled + value.length > limit) {
      await reader.cancel()
      return null
    }
    body.set(value, filled)
    filled += value.length
  }
}

/** Downloads the whole artifact once and keeps only the member's bytes. */
export async function downloadSnapshotMember(
  transport: SnapshotTransport,
  modelId: string,
  source: SnapshotSourceRef,
  memberOffset: number,
  memberSize: number,
  maxBytes: number,
  signal?: AbortSignal,
): Promise<Uint8Array> {
  if (memberSize > maxBytes) throw new SnapshotSourceTooLargeError(modelId, memberSize, maxBytes)
  const location = toSourceLocation(source)
  const response = await fetchOrExpire(transport, modelId, location, { signal })
  if (!response.ok || !response.body) {
    throw await failedResponseError(modelId, location, response, 'Snapshot download')
  }
  await rejectPage(modelId, response)
  const member = new Uint8Array(memberSize)
  const memberEnd = memberOffset + memberSize
  const reader = response.body.getReader()
  let position = 0
  let filled = 0
  while (filled < memberSize) {
    const { done, value } = await reader.read()
    if (done) break
    const from = Math.max(memberOffset, position)
    const to = Math.min(memberEnd, position + value.length)
    if (to > from) {
      member.set(value.subarray(from - position, to - position), from - memberOffset)
      filled += to - from
    }
    position += value.length
  }
  if (filled < memberSize) {
    throw new SnapshotFormatError(
      modelId,
      `member is truncated: got ${filled} of ${memberSize} bytes`,
    )
  }
  await reader.cancel()
  return member
}

/**
 * A snapshot member read page by page over HTTP Range through a chunk cache. A body of any
 * length other than the one asked for means the storage ignored Range or cut the transfer
 * short; that latches, so a short body is never taken for zero-filled pages.
 */
export class HttpRangeFile implements RangeFile {
  readonly cache: RangeChunkCache
  location: SnapshotSourceLocation
  // Each wrong answer may have cost a whole-object download, so it is never asked again.
  private latched: SnapshotRangeUnsupportedError | SnapshotSourcePageError | null = null

  constructor(
    private readonly modelId: string,
    source: SnapshotSourceRef,
    private readonly memberOffset: number,
    readonly size: number,
    private readonly readRangeSync: SyncReadRange,
    cacheOptions: Partial<RangeCacheOptions> = {},
  ) {
    this.location = toSourceLocation(source)
    this.cache = new RangeChunkCache(
      (offset, length) => this.fetch(offset, length),
      size,
      cacheOptions,
    )
  }

  read(offset: number, length: number): Uint8Array {
    return this.cache.read(offset, length)
  }

  /** The latched failure every later read throws; null while reads work. */
  get failure(): SnapshotRangeUnsupportedError | SnapshotSourcePageError | null {
    return this.latched
  }

  /** Hands the cache bytes from the member's start that were already fetched. */
  seed(head: Uint8Array): void {
    this.cache.seed(head)
  }

  private fetch(offset: number, length: number): Uint8Array {
    if (this.latched) throw this.latched
    let bytes: Uint8Array
    try {
      bytes = this.readRangeSync(this.location, this.memberOffset + offset, length)
    } catch (error) {
      if (error instanceof RangeNotHonouredError) throw this.latchRangeUnsupported(error.message)
      if (error instanceof RangePageAnswerError) {
        this.latched = new SnapshotSourcePageError(this.modelId)
        throw this.latched
      }
      if (error instanceof RedirectDroppedHeadersError) {
        throw new SnapshotSourceRedirectError(this.modelId, error.message)
      }
      // Not an expired URL: renewing it would only wait as long again.
      if (errorName(error) === 'TimeoutError') {
        throw new SnapshotSourceTimeoutError(this.modelId, SYNC_RANGE_TIMEOUT_MS)
      }
      // A failed sync XHR's message names the URL, signature included.
      const reason = error instanceof RangeStatusError ? error.message : errorName(error)
      throw new SnapshotSourceExpiredError(this.modelId, `Snapshot range read failed: ${reason}`)
    }
    if (bytes.length !== length) {
      throw this.latchRangeUnsupported(`Range request returned ${bytes.length} of ${length} bytes`)
    }
    return bytes
  }

  private latchRangeUnsupported(reason: string): SnapshotRangeUnsupportedError {
    const error = new SnapshotRangeUnsupportedError(
      this.modelId,
      `Storage stopped honouring Range requests for snapshot '${this.modelId}': ${reason}`,
    )
    this.latched = error
    return error
  }
}

export class BufferRangeFile implements RangeFile {
  readonly size: number

  constructor(private readonly bytes: Uint8Array) {
    this.size = bytes.length
  }

  read(offset: number, length: number): Uint8Array {
    return this.bytes.subarray(offset, offset + length)
  }
}
