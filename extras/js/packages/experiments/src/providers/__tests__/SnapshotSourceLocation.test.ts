import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  SnapshotRangeUnsupportedError,
  SnapshotSourceExpiredError,
  SnapshotSourceRedirectError,
} from '../snapshot-source/errors'
import {
  createSyncRangeReader,
  downloadSnapshotMember,
  HttpRangeFile,
  probeSnapshotHeader,
  xhrReadRange,
  type SnapshotTransport,
  type SyncRangeResponse,
} from '../snapshot-source/httpSource'
import {
  redirectDroppedHeaders,
  sameSourceLocation,
  toSourceLocation,
} from '../snapshot-source/sourceLocation'
import { indexTar, readFixtureTar } from './helpers/snapshotSources'

const ARTIFACT = readFixtureTar('g_raw_sdk_0_5_0')
const [MEMBER_OFFSET, MEMBER_SIZE] = indexTar(ARTIFACT)['exp.db']!
const FILES_URL = 'https://workspace.test/api/2.0/fs/files/a.tar'
const TOKEN = { Authorization: 'Bearer t1' }

describe('source locations', () => {
  it('treats a bare URL as a location without headers', () => {
    expect(toSourceLocation('https://bucket/a?sig=1')).toEqual({ url: 'https://bucket/a?sig=1' })
    expect(sameSourceLocation('https://bucket/a?sig=1', { url: 'https://bucket/a?sig=1' })).toBe(
      true,
    )
  })

  it('tells a renewed token for the same URL apart, whatever the header name case', () => {
    const first = { url: FILES_URL, headers: TOKEN }
    expect(
      sameSourceLocation(first, { url: FILES_URL, headers: { authorization: 'Bearer t1' } }),
    ).toBe(true)
    expect(
      sameSourceLocation(first, { url: FILES_URL, headers: { Authorization: 'Bearer t2' } }),
    ).toBe(false)
    expect(sameSourceLocation(first, { ...first, credentials: 'include' })).toBe(false)
  })

  it('flags only a cross-origin final URL of a request that carried headers', () => {
    const withToken = { url: FILES_URL, headers: TOKEN }
    expect(redirectDroppedHeaders(withToken, 'https://storage.test/blob?sig=1')).toBe(true)
    expect(redirectDroppedHeaders(withToken, `${FILES_URL}?x=1`)).toBe(false)
    expect(redirectDroppedHeaders({ url: FILES_URL }, 'https://storage.test/blob')).toBe(false)
    expect(redirectDroppedHeaders(withToken, '')).toBe(false)
  })
})

function recordingTransport(response: () => Response) {
  const calls: { url: string; init: RequestInit | undefined }[] = []
  const transport: SnapshotTransport = {
    fetch: async (input, init) => {
      calls.push({ url: String(input), init })
      return response()
    },
    readRangeSync: () => new Uint8Array(),
  }
  return { transport, calls }
}

function redirectedResponse(status: number, finalUrl: string): Response {
  const response = new Response('denied', { status })
  Object.defineProperty(response, 'redirected', { value: true })
  Object.defineProperty(response, 'url', { value: finalUrl })
  return response
}

describe('probe and full download with a location', () => {
  it('sends the location headers and credentials mode with Range, and nothing else', async () => {
    const body = ARTIFACT.slice(MEMBER_OFFSET, MEMBER_OFFSET + 100)
    const { transport, calls } = recordingTransport(() => new Response(body, { status: 206 }))
    const location = { url: FILES_URL, headers: TOKEN, credentials: 'include' as const }

    await probeSnapshotHeader(transport, 'm', location, MEMBER_OFFSET, MEMBER_SIZE)

    expect(calls).toEqual([
      {
        url: FILES_URL,
        init: {
          headers: { ...TOKEN, Range: `bytes=${MEMBER_OFFSET}-${MEMBER_OFFSET + 99}` },
          signal: undefined,
          credentials: 'include',
        },
      },
    ])
  })

  it('sends only Range for a bare presigned URL', async () => {
    const { transport, calls } = recordingTransport(
      () => new Response(ARTIFACT.slice(0, 100), { status: 206 }),
    )

    await probeSnapshotHeader(transport, 'm', 'https://bucket/a?sig=1', 0, MEMBER_SIZE)

    expect(calls[0]!.init).toEqual({ headers: { Range: 'bytes=0-99' }, signal: undefined })
  })

  it('reports a failure behind a cross-origin redirect that dropped the token as a redirect', async () => {
    const { transport } = recordingTransport(() =>
      redirectedResponse(401, 'https://storage.test/blob?hop=1'),
    )
    const location = { url: FILES_URL, headers: TOKEN }

    await expect(
      probeSnapshotHeader(transport, 'm', location, 0, MEMBER_SIZE),
    ).rejects.toBeInstanceOf(SnapshotSourceRedirectError)
    await expect(
      downloadSnapshotMember(transport, 'm', location, 0, 1024, 4096),
    ).rejects.toBeInstanceOf(SnapshotSourceRedirectError)
  })

  it('still renews a redirected presigned URL that failed', async () => {
    const { transport } = recordingTransport(() =>
      redirectedResponse(403, 'https://storage.test/blob?sig=1'),
    )

    await expect(
      probeSnapshotHeader(transport, 'm', 'https://proxy.test/a?sig=1', 0, MEMBER_SIZE),
    ).rejects.toBeInstanceOf(SnapshotSourceExpiredError)
  })
})

function rangeBody(range: string | undefined): Uint8Array {
  const match = /^bytes=(\d+)-(\d+)$/.exec(range ?? '')
  return match ? ARTIFACT.slice(Number(match[1]), Number(match[2]) + 1) : ARTIFACT
}

describe('synchronous range reads with a location', () => {
  afterEach(() => vi.unstubAllGlobals())

  function stubXhr(status: number, responseURL: string) {
    const sent: { headers: Record<string, string>; withCredentials: boolean }[] = []
    class FakeXhr {
      status = 0
      response: ArrayBuffer | null = null
      responseType = ''
      responseURL = ''
      withCredentials = false
      private headers: Record<string, string> = {}
      open() {}
      setRequestHeader(name: string, value: string) {
        this.headers[name] = value
      }
      send() {
        sent.push({ headers: this.headers, withCredentials: this.withCredentials })
        this.status = status
        this.responseURL = responseURL
        this.response = new Uint8Array(4).buffer
      }
      getAllResponseHeaders() {
        return ''
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
    return sent
  }

  it('sets the location headers and credentials on the sync XHR', () => {
    const sent = stubXhr(206, FILES_URL)

    xhrReadRange({ url: FILES_URL, headers: TOKEN, credentials: 'include' }, 10, 4)
    xhrReadRange('https://bucket/a?sig=1', 10, 4)

    expect(sent).toEqual([
      { headers: { ...TOKEN, Range: 'bytes=10-13' }, withCredentials: true },
      { headers: { Range: 'bytes=10-13' }, withCredentials: false },
    ])
  })

  it('fails a read behind a redirect that dropped the token with a typed error, not latched', () => {
    let status = 401
    const read = createSyncRangeReader(
      (_location, headers): SyncRangeResponse => ({
        status,
        url: 'https://storage.test/blob?hop=1',
        contentRange: null,
        body: rangeBody(headers.Range),
      }),
    )
    const file = new HttpRangeFile('m', { url: FILES_URL, headers: TOKEN }, 0, MEMBER_SIZE, read)

    expect(() => file.read(0, 100)).toThrow(SnapshotSourceRedirectError)
    expect(() => file.read(0, 100)).not.toThrow(SnapshotRangeUnsupportedError)
    status = 206
    expect(file.read(0, 100)).toEqual(ARTIFACT.slice(0, 100))
  })
})
