export const SNAPSHOT_SOURCE_EXPIRED = 'snapshot-source-expired'
export const SNAPSHOT_RANGE_UNSUPPORTED = 'snapshot-range-unsupported'
export const SNAPSHOT_SOURCE_REDIRECT = 'snapshot-source-redirect'
export const SNAPSHOT_SOURCE_TOO_LARGE = 'snapshot-source-too-large'
export const SNAPSHOT_SOURCE_PAGE = 'snapshot-source-page'
export const SNAPSHOT_TOO_LARGE_FOR_BROWSER = 'snapshot-too-large-for-browser'
export const SNAPSHOT_FORMAT = 'snapshot-format'
/** The same code as a metric request that got no answer in time. */
export const SNAPSHOT_SOURCE_TIMED_OUT = 'timed-out'

/**
 * A request for snapshot bytes failed. Presigned URLs can expire earlier than the platform
 * expects, so callers treat any failed request as a reason to renew the URL once.
 */
export class SnapshotSourceExpiredError extends Error {
  readonly code = SNAPSHOT_SOURCE_EXPIRED

  constructor(
    readonly modelId: string,
    message: string,
  ) {
    super(message)
    this.name = 'SnapshotSourceExpiredError'
  }
}

/**
 * The storage answered a Range read with other bytes than were asked for (a 200 with the whole
 * object, a wrong length or a wrong `Content-Range`). A renewed URL cannot fix that, so the
 * error is not retried, and the file that saw it fails every later read without a request.
 */
export class SnapshotRangeUnsupportedError extends Error {
  readonly code = SNAPSHOT_RANGE_UNSUPPORTED

  constructor(
    readonly modelId: string,
    message: string,
  ) {
    super(message)
    this.name = 'SnapshotRangeUnsupportedError'
  }
}

/**
 * A request that carried storage headers (`Authorization`) was redirected to another origin,
 * which the browser reached without them, and failed there. A renewed token is dropped the
 * same way, so the error is not retried.
 */
export class SnapshotSourceRedirectError extends Error {
  readonly code = SNAPSHOT_SOURCE_REDIRECT

  constructor(
    readonly modelId: string,
    message: string,
  ) {
    super(message)
    this.name = 'SnapshotSourceRedirectError'
  }
}

/**
 * A range read got no answer in time. Not an expired URL: a renewed one would wait as long
 * again, so it is not renewed, and the next read sends a new request.
 */
export class SnapshotSourceTimeoutError extends Error {
  readonly code = SNAPSHOT_SOURCE_TIMED_OUT

  constructor(
    readonly modelId: string,
    readonly limit: number,
  ) {
    super(`Snapshot range read got no answer within ${Math.round(limit / 1000)} s`)
    this.name = 'SnapshotSourceTimeoutError'
  }
}

/** The storage ignored Range and the member is above the full-download cap. */
export class SnapshotSourceTooLargeError extends Error {
  readonly code = SNAPSHOT_SOURCE_TOO_LARGE

  constructor(
    readonly modelId: string,
    readonly size: number,
    readonly limit: number,
  ) {
    super(
      `Experiment snapshot of model '${modelId}' is ${size} bytes; full downloads are limited to ${limit} bytes`,
    )
    this.name = 'SnapshotSourceTooLargeError'
  }
}

/** The zipped database inflates to more bytes than a browser can hold in one buffer. */
export class SnapshotTooLargeForBrowserError extends Error {
  readonly code = SNAPSHOT_TOO_LARGE_FOR_BROWSER

  constructor(
    readonly modelId: string,
    readonly size: number,
    readonly limit: number,
  ) {
    super(
      `Experiment snapshot of model '${modelId}' unzips to ${size} bytes; the browser limit is ${limit} bytes`,
    )
    this.name = 'SnapshotTooLargeForBrowserError'
  }
}

/**
 * The storage answered with a web page instead of snapshot bytes, usually a sign-in page that
 * an expired token was redirected to. It is reported, not renewed: nothing tells such a page
 * from a storage that answers every request with HTML.
 */
export class SnapshotSourcePageError extends Error {
  readonly code = SNAPSHOT_SOURCE_PAGE

  constructor(readonly modelId: string) {
    super(`Experiment snapshot of model '${modelId}' was answered with a web page, not its data`)
    this.name = 'SnapshotSourcePageError'
  }
}

export class SnapshotFormatError extends Error {
  readonly code = SNAPSHOT_FORMAT

  constructor(
    readonly modelId: string,
    reason: string,
  ) {
    super(`Experiment snapshot of model '${modelId}' cannot be read: ${reason}`)
    this.name = 'SnapshotFormatError'
  }
}

export function isSnapshotSourceExpired(error: unknown): error is SnapshotSourceExpiredError {
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as { code?: unknown }).code === SNAPSHOT_SOURCE_EXPIRED &&
    typeof (error as { modelId?: unknown }).modelId === 'string'
  )
}

export function isSnapshotRangeUnsupported(error: unknown): error is SnapshotRangeUnsupportedError {
  return (
    typeof error === 'object' &&
    error !== null &&
    (error as { code?: unknown }).code === SNAPSHOT_RANGE_UNSUPPORTED &&
    typeof (error as { modelId?: unknown }).modelId === 'string'
  )
}

type CodedSnapshotError =
  | SnapshotSourceExpiredError
  | SnapshotRangeUnsupportedError
  | SnapshotSourceRedirectError
  | SnapshotSourceTooLargeError
  | SnapshotTooLargeForBrowserError
  | SnapshotSourcePageError
  | SnapshotFormatError
  | SnapshotSourceTimeoutError

export type SnapshotErrorCode = CodedSnapshotError['code']

/** The fields that carry a typed source error across the worker boundary. */
export interface SnapshotErrorFields {
  code: SnapshotErrorCode
  modelId: string
  size?: number
  limit?: number
}

const CODED_ERRORS = new Set<string>([
  SNAPSHOT_SOURCE_EXPIRED,
  SNAPSHOT_RANGE_UNSUPPORTED,
  SNAPSHOT_SOURCE_REDIRECT,
  SNAPSHOT_SOURCE_TOO_LARGE,
  SNAPSHOT_TOO_LARGE_FOR_BROWSER,
  SNAPSHOT_SOURCE_PAGE,
  SNAPSHOT_FORMAT,
  SNAPSHOT_SOURCE_TIMED_OUT,
])

export function snapshotErrorFields(error: unknown): SnapshotErrorFields | null {
  if (typeof error !== 'object' || error === null) return null
  const { code, modelId, size, limit } = error as Record<string, unknown>
  if (typeof code !== 'string' || !CODED_ERRORS.has(code) || typeof modelId !== 'string') {
    return null
  }
  const fields: SnapshotErrorFields = { code: code as SnapshotErrorCode, modelId }
  if (typeof size === 'number') fields.size = size
  if (typeof limit === 'number') fields.limit = limit
  return fields
}

/** Rebuilds the typed error a worker reported with `snapshotErrorFields`. */
export function snapshotErrorFromFields(fields: SnapshotErrorFields, message: string): Error {
  switch (fields.code) {
    case SNAPSHOT_SOURCE_EXPIRED:
      return new SnapshotSourceExpiredError(fields.modelId, message)
    case SNAPSHOT_RANGE_UNSUPPORTED:
      return new SnapshotRangeUnsupportedError(fields.modelId, message)
    case SNAPSHOT_SOURCE_REDIRECT:
      return new SnapshotSourceRedirectError(fields.modelId, message)
    case SNAPSHOT_SOURCE_TOO_LARGE:
      return new SnapshotSourceTooLargeError(fields.modelId, fields.size ?? 0, fields.limit ?? 0)
    case SNAPSHOT_TOO_LARGE_FOR_BROWSER:
      return new SnapshotTooLargeForBrowserError(
        fields.modelId,
        fields.size ?? 0,
        fields.limit ?? 0,
      )
    case SNAPSHOT_SOURCE_PAGE:
      return new SnapshotSourcePageError(fields.modelId)
    case SNAPSHOT_SOURCE_TIMED_OUT:
      return new SnapshotSourceTimeoutError(fields.modelId, fields.limit ?? 0)
    case SNAPSHOT_FORMAT: {
      const error = new SnapshotFormatError(fields.modelId, '')
      error.message = message
      return error
    }
  }
}

const ABSOLUTE_URL = /\b[a-z][a-z\d+.-]*:\/\/[^\s'"<>]+/gi
const QUERY_STRING = /\?[^\s'"<>]*=[^\s'"<>]*/g
const CREDENTIAL = /\b(bearer|basic|token)\s+[^\s'"<>]+/gi
const SHARED_ACCESS_SIGNATURE = /\bSharedAccessSignature\s+[^\s'"<>]+/gi
const SIGNATURE_PAIR = /\b([\w-]*(?:sig|signature|credential|token|key)[\w-]*)=[^\s&'"<>]+/gi
const SECRET_HEADER = /\b(x-amz-security-token|x-ms-[\w-]+)(\s*[:=]\s*)[^\s'"<>,;]+/gi
const JWT = /\beyJ[\w-]+\.[\w-]+\.[\w-]+/g

function originOf(url: string): string {
  try {
    const { origin } = new URL(url)
    return origin === 'null' ? '[url]' : origin
  } catch {
    return '[url]'
  }
}

/**
 * Text that is safe to show or log: absolute URLs are cut to their origin, query strings and
 * credentials removed. Presigned URLs carry their signature in the query and browsers put the
 * URL into network error messages, so every message that leaves the provider passes here,
 * whatever produced it. The other patterns (signature pairs, SAS, JWTs, storage headers) are
 * defence in depth: messages are built without secrets in the first place.
 */
export function redactSecrets(text: string): string {
  return text
    .replace(ABSOLUTE_URL, originOf)
    .replace(QUERY_STRING, '?[redacted]')
    .replace(SHARED_ACCESS_SIGNATURE, 'SharedAccessSignature [redacted]')
    .replace(CREDENTIAL, '$1 [redacted]')
    .replace(SECRET_HEADER, '$1$2[redacted]')
    .replace(SIGNATURE_PAIR, '$1=[redacted]')
    .replace(JWT, '[redacted]')
}

/** A thrown value named by its type only: its message may carry a URL. */
export function errorName(error: unknown): string {
  const name = (error as { name?: unknown } | null)?.name
  return typeof name === 'string' && /^\w+$/.test(name) ? name : 'Error'
}
