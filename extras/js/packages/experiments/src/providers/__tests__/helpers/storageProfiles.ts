// Storage behaviours the snapshot transport must cope with, served by vitest's browser-like
// memory transport and by the Playwright spec's two-origin HTTP server alike. A new storage
// type is one more entry in STORAGE_PROFILES.
import type { SnapshotSourceRef } from '../../snapshot-source/sourceLocation'

/** `page` is the viewer's own origin (a same-origin proxy); `storage` is a second origin. */
export type StorageHost = 'page' | 'storage'

export interface StorageOrigins {
  page: string
  storage: string
}

export type StorageAuth = 'query-sig' | 'sas' | 'bearer' | 'session-cookie'

/**
 * `echo-origin`: the request's origin is allowed and the storage headers are exposed.
 * `any-origin`: `*` on every answer, nothing exposed. `none`: no CORS headers at all.
 */
export type StorageCors = 'echo-origin' | 'any-origin' | 'none'

interface StorageAnswer {
  status: number
  contentType: string
  body: string
}

export interface StorageProfile {
  name: string
  host: StorageHost
  auth: StorageAuth
  /** A ranged GET is honoured with 206 or 200, or answered with the whole object. */
  rangeAnswer: 206 | 200 | 'whole'
  /** Whether a whole-object answer declares Content-Length; a buffering proxy may not. */
  wholeLength: boolean
  cors: StorageCors
  exposeContentRange: boolean
  extraHeaders: Readonly<Record<string, string>>
  /** A revoked, expired or wrong credential. */
  expired: StorageAnswer
  /** A bearer storage's answer to a request without Authorization; `expired` when null. */
  unauthenticated: StorageAnswer | null
  /** The issued URL answers with a redirect to a presigned URL on the storage origin. */
  redirect: { status: 302 | 307; targetNeedsAuth: boolean } | null
  preflightMaxAge: number | null
  /** Sent on every answer instead of the headers a preflight asked for; null to echo them. */
  allowHeaders: string | null
  /** `network-error`: the browser refuses the answers, so the open fails. */
  expected: 'raw-range' | 'raw-full' | 'redirect-error' | 'network-error'
  /** The storage may start ignoring Range mid-session (an S3 clone or a proxy). */
  rangeMayStop: boolean
}

const S3_EXPIRED = {
  status: 403,
  contentType: 'application/xml',
  body: '<?xml version="1.0" encoding="UTF-8"?><Error><Code>AccessDenied</Code><Message>Request has expired</Message></Error>',
}
const AZURE_EXPIRED = {
  status: 403,
  contentType: 'application/xml',
  body: '<?xml version="1.0" encoding="utf-8"?><Error><Code>AuthenticationFailed</Code><Message>Signed expiry time has to be after signed start time</Message></Error>',
}
// A generic bearer API behind a redirecting proxy.
const TOKEN_EXPIRED = {
  status: 401,
  contentType: 'application/json',
  body: '{"error_code":"UNAUTHENTICATED","message":"Token is expired."}',
}
// The Databricks workspace Files API 2.0, as measured live on 2026-11-17.
const DATABRICKS_INVALID_TOKEN = {
  status: 403,
  contentType: 'application/json; charset=utf-8',
  body: '{"error_code":403,"message":"Invalid access token. [ReqId: ef12c1e2-68d4-4ccc-809a-dbe0c6cb3d69]"}',
}
const DATABRICKS_NO_TOKEN = {
  status: 401,
  contentType: 'application/json; charset=utf-8',
  body: '{"error_code":401,"message":"Credential was not sent or was of an unsupported type for this API. [ReqId: 11321611-38a9-4cd7-a02c-df0e4f6362d8]"}',
}
const DATABRICKS_HEADERS = {
  'x-request-id': 'f1c2d3e4-0000-4000-8000-000000000001',
  'cache-control': 'no-cache, no-store, must-revalidate',
  expires: '0',
  pragma: 'no-cache',
  'content-disposition': 'attachment',
}
const DATABRICKS_ALLOW_HEADERS =
  'Authorization, X-Databricks-Azure-Workspace-Resource-Id, X-Databricks-Org-Id, Content-Type, X-Databricks-Attribution-Tags'
const PROXY_EXPIRED = { status: 403, contentType: 'text/plain', body: 'expired' }
const AZURE_HEADERS = {
  'x-ms-request-id': 'b1c2d3',
  'x-ms-version': '2025-01-05',
  'x-ms-blob-type': 'BlockBlob',
  'Accept-Ranges': 'bytes',
}

const BASE: Omit<StorageProfile, 'name'> = {
  host: 'storage',
  auth: 'query-sig',
  rangeAnswer: 206,
  wholeLength: true,
  cors: 'echo-origin',
  exposeContentRange: false,
  extraHeaders: { 'x-amz-request-id': 'A1B2C3' },
  expired: S3_EXPIRED,
  unauthenticated: null,
  redirect: null,
  preflightMaxAge: null,
  allowHeaders: null,
  expected: 'raw-range',
  rangeMayStop: true,
}

function profile(name: string, overrides: Partial<StorageProfile>): StorageProfile {
  return { ...BASE, ...overrides, name }
}

export const STORAGE_PROFILES: StorageProfile[] = [
  profile('s3', {}),
  profile('s3-200', { rangeAnswer: 200 }),
  profile('azure', {
    exposeContentRange: true,
    extraHeaders: AZURE_HEADERS,
    expired: AZURE_EXPIRED,
    rangeMayStop: false,
  }),
  profile('azure-sas', {
    auth: 'sas',
    exposeContentRange: true,
    extraHeaders: AZURE_HEADERS,
    expired: AZURE_EXPIRED,
    rangeMayStop: false,
  }),
  profile('databricks-files-api', {
    auth: 'bearer',
    cors: 'any-origin',
    extraHeaders: DATABRICKS_HEADERS,
    expired: DATABRICKS_INVALID_TOKEN,
    unauthenticated: DATABRICKS_NO_TOKEN,
    allowHeaders: DATABRICKS_ALLOW_HEADERS,
    rangeMayStop: false,
  }),
  // Databricks presigned download URLs answer without any CORS header.
  profile('no-cors', {
    cors: 'none',
    extraHeaders: {},
    expected: 'network-error',
    rangeMayStop: false,
  }),
  profile('proxy', { host: 'page', extraHeaders: {}, expired: PROXY_EXPIRED }),
  profile('proxy-cors-cookie', {
    auth: 'session-cookie',
    exposeContentRange: true,
    extraHeaders: {},
    expired: PROXY_EXPIRED,
  }),
  profile('proxy-redirect', {
    host: 'page',
    extraHeaders: {},
    redirect: { status: 307, targetNeedsAuth: false },
  }),
  profile('bearer-redirect', {
    host: 'page',
    auth: 'bearer',
    extraHeaders: {},
    expired: TOKEN_EXPIRED,
    redirect: { status: 302, targetNeedsAuth: false },
    preflightMaxAge: 600,
    rangeMayStop: false,
  }),
  profile('bearer-redirect-needs-token', {
    host: 'page',
    auth: 'bearer',
    extraHeaders: {},
    expired: TOKEN_EXPIRED,
    redirect: { status: 307, targetNeedsAuth: true },
    preflightMaxAge: 600,
    expected: 'redirect-error',
    rangeMayStop: false,
  }),
  profile('proxy-buffering', {
    rangeAnswer: 'whole',
    extraHeaders: {},
    expired: PROXY_EXPIRED,
    expected: 'raw-full',
    rangeMayStop: false,
  }),
  profile('proxy-buffering-chunked', {
    rangeAnswer: 'whole',
    wholeLength: false,
    extraHeaders: {},
    expired: PROXY_EXPIRED,
    expected: 'raw-full',
    rangeMayStop: false,
  }),
]

/** An Azure SAS query; percent-encoded as Azure issues it, so re-encoding it breaks it. */
export function sasQuery(credential: string): string {
  return `sv=2025-01-05&se=2026-11-15T12%3A00%3A00Z&sr=b&sp=r&sig=k${credential}%2Bv%2F0%3D`
}

export const SESSION_COOKIE = 'luml_session=1'

function objectPath(profile: StorageProfile, artifact: string): string {
  return `/o/${profile.name}/${artifact}`
}

/** The location the platform would hand out for credential generation `credential`. */
export function issueLocation(
  profile: StorageProfile,
  origins: StorageOrigins,
  artifact: string,
  credential: string,
): SnapshotSourceRef {
  const url = `${origins[profile.host]}${objectPath(profile, artifact)}`
  switch (profile.auth) {
    case 'query-sig':
      return `${url}?sig=${credential}`
    case 'sas':
      return `${url}?${sasQuery(credential)}`
    case 'bearer':
      return { url, headers: { Authorization: `Bearer tok-${credential}` } }
    case 'session-cookie':
      return { url: `${url}?sig=${credential}`, credentials: 'include' }
  }
}

export interface StorageRequest {
  host: StorageHost
  method: string
  /** Path and query exactly as received. */
  target: string
  /** Lower-case names. */
  headers: Readonly<Record<string, string | undefined>>
}

export interface StorageResponse {
  status: number
  headers: Record<string, string>
  body: Uint8Array
  /** The connection drops after this many body bytes, as a cut transfer does. */
  dropAfter?: number
}

export interface LoggedStorageRequest {
  profile: string
  artifact: string
  host: StorageHost
  method: string
  credential: string | null
  range: string | null
  status: number
  bytes: number
  /** Request headers other than the ones every browser request carries. */
  extraHeaders: string[]
}

export interface StorageState {
  revoked: Set<string>
  rejectAll: boolean
  ignoreRange: boolean
  /** Ranged reads that start at or after this artifact offset are cut short. */
  truncateFrom: number | null
  truncation: 'short-206' | 'dropped'
  log: LoggedStorageRequest[]
}

export function newStorageState(): StorageState {
  return {
    revoked: new Set(),
    rejectAll: false,
    ignoreRange: false,
    truncateFrom: null,
    truncation: 'short-206',
    log: [],
  }
}

export interface StorageContext {
  origins: StorageOrigins
  state: StorageState
  object(artifact: string): Uint8Array | undefined
}

const STANDARD_REQUEST_HEADERS = new Set([
  'host',
  'connection',
  'origin',
  'referer',
  'user-agent',
  'accept',
  'accept-encoding',
  'accept-language',
  'range',
  'cookie',
  'pragma',
  'cache-control',
  'content-length',
])

function extraRequestHeaders(headers: StorageRequest['headers']): string[] {
  return Object.keys(headers)
    .filter((name) => !STANDARD_REQUEST_HEADERS.has(name) && !name.startsWith('sec-'))
    .sort()
}

function queryParam(target: string, name: string): string | null {
  return new RegExp(`[?&]${name}=([^&]*)`).exec(target)?.[1] ?? null
}

function credentialOf(profile: StorageProfile, request: StorageRequest, hop: boolean) {
  if (hop)
    return profile.redirect?.targetNeedsAuth ? bearerOf(request) : queryParam(request.target, 'sig')
  switch (profile.auth) {
    case 'query-sig':
      return queryParam(request.target, 'sig')
    case 'sas': {
      const credential = /[?&]sig=k(\d+)%2Bv%2F0%3D$/.exec(request.target)?.[1] ?? null
      const query = request.target.slice(request.target.indexOf('?') + 1)
      return credential !== null && query === sasQuery(credential) ? credential : null
    }
    case 'bearer':
      return bearerOf(request)
    case 'session-cookie':
      return request.headers.cookie?.includes(SESSION_COOKIE)
        ? queryParam(request.target, 'sig')
        : null
  }
}

function bearerOf(request: StorageRequest): string | null {
  return /^Bearer tok-(\d+)$/.exec(request.headers.authorization ?? '')?.[1] ?? null
}

function corsHeaders(profile: StorageProfile, request: StorageRequest): Record<string, string> {
  if (profile.cors === 'none') return {}
  if (profile.cors === 'any-origin') {
    return {
      'Access-Control-Allow-Origin': '*',
      ...(profile.allowHeaders ? { 'Access-Control-Allow-Headers': profile.allowHeaders } : {}),
    }
  }
  const origin = request.headers.origin
  if (!origin) return {}
  const exposed = [...Object.keys(profile.extraHeaders), 'ETag']
  if (profile.exposeContentRange) exposed.push('Content-Range')
  return {
    'Access-Control-Allow-Origin': origin,
    Vary: 'Origin',
    'Access-Control-Expose-Headers': exposed.join(', '),
    ...(profile.auth === 'session-cookie' ? { 'Access-Control-Allow-Credentials': 'true' } : {}),
  }
}

function preflight(profile: StorageProfile, request: StorageRequest): StorageResponse {
  if (profile.cors === 'none') return { status: 500, headers: {}, body: new Uint8Array(0) }
  if (profile.cors === 'any-origin') {
    return { status: 200, headers: corsHeaders(profile, request), body: new Uint8Array(0) }
  }
  const allowed = profile.auth === 'bearer' ? 'range, authorization' : 'range'
  return {
    status: 200,
    headers: {
      ...corsHeaders(profile, request),
      'Access-Control-Allow-Methods': 'GET, HEAD',
      'Access-Control-Allow-Headers': allowed,
      ...(profile.preflightMaxAge === null
        ? {}
        : { 'Access-Control-Max-Age': String(profile.preflightMaxAge) }),
    },
    body: new Uint8Array(0),
  }
}

function whole(bytes: Uint8Array, withLength: boolean): StorageResponse {
  return {
    status: 200,
    headers: withLength ? { 'Content-Length': String(bytes.length) } : {},
    body: bytes,
  }
}

function ranged(
  profile: StorageProfile,
  state: StorageState,
  bytes: Uint8Array,
  start: number,
  end: number,
): StorageResponse {
  const last = Math.min(end, bytes.length - 1)
  const body = bytes.subarray(start, last + 1)
  const contentRange = (to: number) => ({ 'Content-Range': `bytes ${start}-${to}/${bytes.length}` })
  if (state.truncateFrom !== null && start >= state.truncateFrom) {
    const kept = Math.floor(body.length / 2)
    if (state.truncation === 'dropped') {
      return {
        status: 206,
        headers: { 'Content-Length': String(body.length), ...contentRange(last) },
        body,
        dropAfter: kept,
      }
    }
    return {
      status: 206,
      headers: { 'Content-Length': String(kept), ...contentRange(start + kept - 1) },
      body: body.subarray(0, kept),
    }
  }
  return {
    status: profile.rangeAnswer === 200 ? 200 : 206,
    headers: {
      'Content-Length': String(body.length),
      ...(profile.rangeAnswer === 200 ? {} : contentRange(last)),
    },
    body,
  }
}

function answer(
  profile: StorageProfile,
  request: StorageRequest,
  context: StorageContext,
  artifact: string,
): StorageResponse {
  const { state, origins } = context
  const hop = queryParam(request.target, 'hop') === '1'
  const credential = credentialOf(profile, request, hop)
  const bytes = context.object(artifact)
  if (!bytes) return { status: 404, headers: {}, body: new Uint8Array(0) }
  if (credential === null || state.rejectAll || state.revoked.has(credential)) {
    const unauthenticated = !hop && profile.auth === 'bearer' && !request.headers.authorization
    const { status, contentType, body } =
      (unauthenticated && profile.unauthenticated) || profile.expired
    return {
      status,
      headers: { 'Content-Type': contentType },
      body: new TextEncoder().encode(body),
    }
  }
  if (profile.redirect && !hop) {
    const location = `${origins.storage}${objectPath(profile, artifact)}?sig=${credential}&hop=1`
    return {
      status: profile.redirect.status,
      headers: { Location: location },
      body: new Uint8Array(0),
    }
  }
  const range = /^bytes=(\d+)-(\d+)$/.exec(request.headers.range ?? '')
  if (!range) return whole(bytes, true)
  if (profile.rangeAnswer === 'whole') return whole(bytes, profile.wholeLength)
  if (state.ignoreRange) return whole(bytes, true)
  return ranged(profile, state, bytes, Number(range[1]), Number(range[2]))
}

const OBJECT_PATH = /^\/o\/([^/]+)\/([^?]+)/

/** Answers a request for `/o/<profile>/<artifact>`; null for any other path. */
export function respondAsStorage(
  request: StorageRequest,
  context: StorageContext,
): StorageResponse | null {
  const match = OBJECT_PATH.exec(request.target)
  const profile = STORAGE_PROFILES.find((item) => item.name === match?.[1])
  if (!match || !profile) return null
  const response =
    request.method === 'OPTIONS'
      ? preflight(profile, request)
      : answer(profile, request, context, decodeURIComponent(match[2] ?? ''))
  const hop = queryParam(request.target, 'hop') === '1'
  context.state.log.push({
    profile: profile.name,
    artifact: decodeURIComponent(match[2] ?? ''),
    host: request.host,
    method: request.method,
    credential: request.method === 'OPTIONS' ? null : credentialOf(profile, request, hop),
    range: request.headers.range ?? null,
    status: response.status,
    bytes: response.dropAfter ?? response.body.length,
    extraHeaders: extraRequestHeaders(request.headers),
  })
  response.headers = {
    ...profile.extraHeaders,
    ...response.headers,
    ...(request.method === 'OPTIONS' ? {} : corsHeaders(profile, request)),
  }
  return response
}

/** The answers that carried data or a failure; a redirecting proxy's hops are left out. */
export function dataAnswers(log: LoggedStorageRequest[]): LoggedStorageRequest[] {
  return log.filter(
    (entry) => entry.method === 'GET' && (entry.status < 300 || entry.status >= 400),
  )
}
