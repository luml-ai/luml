import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  SnapshotFormatError,
  SnapshotRangeUnsupportedError,
  SnapshotSourceExpiredError,
  SnapshotSourceTooLargeError,
} from '../snapshot-source/errors'
import {
  downloadSnapshotMember,
  HttpRangeFile,
  probeSnapshotHeader,
  RangeNotHonouredError,
  xhrReadRange,
  type SnapshotTransport,
} from '../snapshot-source/httpSource'
import { openRawSnapshot, DEFAULT_RAW_SNAPSHOT_OPTIONS } from '../snapshot-source/openRawSnapshot'
import { RangeSqliteEngine } from '../snapshot-source/RangeSqliteEngine'
import { validateSqliteHeader } from '../snapshot-source/sqliteHeader'
import type { SnapshotSourceLocation } from '../snapshot-source/sourceLocation'
import { indexTar, memoryTransport, readFixtureTar } from './helpers/snapshotSources'

const ARTIFACT = readFixtureTar('g_raw_sdk_0_5_0')
const [MEMBER_OFFSET, MEMBER_SIZE] = indexTar(ARTIFACT)['exp.db']!
const DB = ARTIFACT.slice(MEMBER_OFFSET, MEMBER_OFFSET + MEMBER_SIZE)
const URL_A = 'https://bucket.test/artifact?sig=a'

function header(mutate: (bytes: Uint8Array) => void = () => {}): Uint8Array {
  const bytes = DB.slice(0, 100)
  mutate(bytes)
  return bytes
}

function transportReturning(response: () => Response): SnapshotTransport {
  return { fetch: async () => response(), readRangeSync: () => new Uint8Array() }
}

describe('validateSqliteHeader', () => {
  it('accepts a 16 KiB page, non-WAL database and reports its geometry', () => {
    expect(validateSqliteHeader('m', header(), MEMBER_SIZE)).toEqual({
      pageSize: 16384,
      pageCount: MEMBER_SIZE / 16384,
    })
  })

  it.each([
    ['not SQLite', (bytes: Uint8Array) => bytes.set([0x50, 0x4b, 0x03, 0x04]), /not an SQLite/],
    ['WAL', (bytes: Uint8Array) => bytes.set([2, 2], 18), /WAL/],
    ['bad page size', (bytes: Uint8Array) => bytes.set([0x30, 0x00], 16), /page size/],
  ])('rejects a %s header', (_label, mutate, message) => {
    expect(() => validateSqliteHeader('m', header(mutate), MEMBER_SIZE)).toThrow(message)
  })

  it('rejects a member that is shorter than the database it describes', () => {
    expect(() => validateSqliteHeader('m', header(), MEMBER_SIZE - 16384)).toThrow(
      SnapshotFormatError,
    )
    expect(() => validateSqliteHeader('m', header(), MEMBER_SIZE - 16384)).toThrow(/truncated/)
  })

  it('rejects a short header', () => {
    expect(() => validateSqliteHeader('m', header().subarray(0, 60), MEMBER_SIZE)).toThrow(
      /60 bytes/,
    )
  })
})

describe('probeSnapshotHeader', () => {
  it('reads the 100 header bytes at the member offset with a Range request', async () => {
    const { transport, requests } = memoryTransport({ [URL_A]: ARTIFACT })

    const probe = await probeSnapshotHeader(transport, 'm', URL_A, MEMBER_OFFSET, MEMBER_SIZE)

    expect(probe).toEqual({ rangeIgnored: false, header: header() })
    expect(requests).toEqual([{ kind: 'fetch', url: URL_A, offset: MEMBER_OFFSET, length: 100 }])
  })

  // Status does not tell: some storages honour Range with a 200. A body longer than asked
  // for is the whole object, abandoned as soon as that is known.
  it('reports an ignored Range from the body length and stops reading it early', async () => {
    const cancel = vi.fn()
    let pulled = 0
    const body = new ReadableStream<Uint8Array>({
      pull(controller) {
        controller.enqueue(ARTIFACT.slice(pulled, pulled + 7000))
        pulled += 7000
      },
      cancel,
    })
    const transport = transportReturning(() => new Response(body, { status: 200 }))

    const probe = await probeSnapshotHeader(transport, 'm', URL_A, MEMBER_OFFSET, MEMBER_SIZE)

    expect(probe).toEqual({ rangeIgnored: true })
    expect(cancel).toHaveBeenCalled()
    expect(pulled).toBeLessThanOrEqual(3 * 7000)
  })

  it('abandons a body whose Content-Length is larger than asked for without reading it', async () => {
    const cancel = vi.fn()
    const pull = vi.fn()
    const body = new ReadableStream<Uint8Array>({ pull, cancel }, { highWaterMark: 0 })
    const transport = transportReturning(
      () =>
        new Response(body, { status: 200, headers: { 'Content-Length': String(ARTIFACT.length) } }),
    )

    const probe = await probeSnapshotHeader(transport, 'm', URL_A, MEMBER_OFFSET, MEMBER_SIZE)

    expect(probe).toEqual({ rangeIgnored: true })
    expect(cancel).toHaveBeenCalled()
    expect(pull).not.toHaveBeenCalled()
  })

  it.each([200, 203, 206])('accepts status %i with exactly the requested bytes', async (status) => {
    const transport = transportReturning(() => new Response(DB.slice(0, 65536), { status }))

    const probe = await probeSnapshotHeader(transport, 'm', URL_A, 0, MEMBER_SIZE, 65536)

    expect(probe).toEqual({ rangeIgnored: false, header: DB.slice(0, 65536) })
  })

  it.each([403, 404, 500])('reports status %i as a source failure to renew', async (status) => {
    const transport = transportReturning(() => new Response('', { status }))

    await expect(
      probeSnapshotHeader(transport, 'm', URL_A, MEMBER_OFFSET, MEMBER_SIZE),
    ).rejects.toMatchObject({ name: 'SnapshotSourceExpiredError', modelId: 'm' })
  })

  it('reports a network failure as a source failure and passes aborts through', async () => {
    const failing: SnapshotTransport = {
      fetch: async () => {
        throw new TypeError('Failed to fetch')
      },
      readRangeSync: () => new Uint8Array(),
    }
    await expect(probeSnapshotHeader(failing, 'm', URL_A, 0, MEMBER_SIZE)).rejects.toBeInstanceOf(
      SnapshotSourceExpiredError,
    )

    const aborting: SnapshotTransport = {
      fetch: async () => {
        throw new DOMException('Aborted', 'AbortError')
      },
      readRangeSync: () => new Uint8Array(),
    }
    await expect(probeSnapshotHeader(aborting, 'm', URL_A, 0, MEMBER_SIZE)).rejects.toMatchObject({
      name: 'AbortError',
    })
  })

  it('rejects a mismatching Content-Range as not renewable, whatever the status', async () => {
    const mismatch200 = transportReturning(
      () =>
        new Response(header(), {
          status: 200,
          headers: { 'Content-Range': `bytes 0-99/${ARTIFACT.length}` },
        }),
    )
    await expect(
      probeSnapshotHeader(mismatch200, 'm', URL_A, MEMBER_OFFSET, MEMBER_SIZE),
    ).rejects.toBeInstanceOf(SnapshotRangeUnsupportedError)

    const otherRange = transportReturning(
      () =>
        new Response(header(), {
          status: 206,
          headers: { 'Content-Range': `bytes 0-99/${ARTIFACT.length}` },
        }),
    )
    await expect(
      probeSnapshotHeader(otherRange, 'm', URL_A, MEMBER_OFFSET, MEMBER_SIZE),
    ).rejects.toThrow(/Content-Range does not match bytes=/)
  })

  it('treats a short body as an ignored Range and rejects a member too small for a header', async () => {
    const short = transportReturning(() => new Response(header().slice(0, 40), { status: 206 }))
    await expect(probeSnapshotHeader(short, 'm', URL_A, 0, MEMBER_SIZE)).resolves.toEqual({
      rangeIgnored: true,
    })
    await expect(probeSnapshotHeader(short, 'm', URL_A, 0, 50)).rejects.toThrow(/truncated/)
  })

  it('reads a whole first chunk, or the whole member when it is smaller', async () => {
    const { transport, requests } = memoryTransport({ [URL_A]: ARTIFACT })

    const chunk = await probeSnapshotHeader(
      transport,
      'm',
      URL_A,
      MEMBER_OFFSET,
      MEMBER_SIZE,
      65536,
    )
    const small = await probeSnapshotHeader(transport, 'm', URL_A, MEMBER_OFFSET, 30_000, 65536)

    expect(chunk).toEqual({ rangeIgnored: false, header: DB.slice(0, 65536) })
    expect(small).toEqual({ rangeIgnored: false, header: DB.slice(0, 30_000) })
    expect(requests).toEqual([
      { kind: 'fetch', url: URL_A, offset: MEMBER_OFFSET, length: 65536 },
      { kind: 'fetch', url: URL_A, offset: MEMBER_OFFSET, length: 30_000 },
    ])
  })

  it('checks a first-chunk answer against the bytes it asked for', async () => {
    const headerOnly = transportReturning(
      () =>
        new Response(DB.slice(0, 65536), {
          status: 206,
          headers: { 'Content-Range': `bytes 0-99/${MEMBER_SIZE}` },
        }),
    )
    await expect(
      probeSnapshotHeader(headerOnly, 'm', URL_A, 0, MEMBER_SIZE, 65536),
    ).rejects.toBeInstanceOf(SnapshotRangeUnsupportedError)

    const short = transportReturning(() => new Response(DB.slice(0, 100), { status: 206 }))
    await expect(probeSnapshotHeader(short, 'm', URL_A, 0, MEMBER_SIZE, 65536)).resolves.toEqual({
      rangeIgnored: true,
    })
  })
})

describe('downloadSnapshotMember', () => {
  function chunkedResponse(bytes: Uint8Array, chunkSize: number): Response {
    let position = 0
    const body = new ReadableStream<Uint8Array>({
      pull(controller) {
        if (position >= bytes.length) return controller.close()
        controller.enqueue(bytes.slice(position, position + chunkSize))
        position += chunkSize
      },
    })
    return new Response(body, { status: 200 })
  }

  it('keeps only the member bytes of a streamed artifact', async () => {
    const transport = transportReturning(() => chunkedResponse(ARTIFACT, 7000))

    const member = await downloadSnapshotMember(
      transport,
      'm',
      URL_A,
      MEMBER_OFFSET,
      MEMBER_SIZE,
      MEMBER_SIZE,
    )

    expect(member).toEqual(DB)
  })

  it('refuses a member above the size cap before downloading', async () => {
    const fetch = vi.fn()
    const transport = { fetch, readRangeSync: () => new Uint8Array() }

    const download = downloadSnapshotMember(transport, 'm', URL_A, 0, 2048, 1024)

    await expect(download).rejects.toBeInstanceOf(SnapshotSourceTooLargeError)
    await expect(download).rejects.toMatchObject({ size: 2048, limit: 1024 })
    expect(fetch).not.toHaveBeenCalled()
  })

  it('rejects a stream that ends inside the member', async () => {
    const transport = transportReturning(() =>
      chunkedResponse(ARTIFACT.slice(0, MEMBER_OFFSET + 10), 4096),
    )

    await expect(
      downloadSnapshotMember(transport, 'm', URL_A, MEMBER_OFFSET, MEMBER_SIZE, MEMBER_SIZE),
    ).rejects.toThrow(/truncated/)
  })
})

describe('xhrReadRange', () => {
  afterEach(() => vi.unstubAllGlobals())

  function stubXhr(status: number, body: Uint8Array, headers = ''): void {
    class FakeXhr {
      status = 0
      response: ArrayBuffer | null = null
      responseType = ''
      open() {}
      setRequestHeader() {}
      send() {
        this.status = status
        this.response = body.slice().buffer
      }
      getAllResponseHeaders() {
        return headers
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXhr)
  }

  const BYTES = new Uint8Array([1, 2, 3, 4])

  it('returns the body of a 206 whose Content-Range matches or is not exposed', () => {
    stubXhr(
      206,
      BYTES,
      'content-type: application/octet-stream\r\ncontent-range: bytes 10-13/99\r\n',
    )
    expect(xhrReadRange(URL_A, 10, 4)).toEqual(BYTES)
    stubXhr(206, BYTES)
    expect(xhrReadRange(URL_A, 10, 4)).toEqual(BYTES)
  })

  it('returns any 2xx body for the caller to check by length', () => {
    stubXhr(200, BYTES)
    expect(xhrReadRange(URL_A, 10, 4)).toEqual(BYTES)
    stubXhr(200, ARTIFACT)
    expect(xhrReadRange(URL_A, 10, 4)).toHaveLength(ARTIFACT.length)
  })

  it('tells a range the server did not honour apart from a failed request', () => {
    stubXhr(206, BYTES, 'Content-Range: bytes 0-3/99\r\n')
    expect(() => xhrReadRange(URL_A, 10, 4)).toThrow(RangeNotHonouredError)
    stubXhr(200, BYTES, 'Content-Range: bytes 0-3/99\r\n')
    expect(() => xhrReadRange(URL_A, 10, 4)).toThrow(RangeNotHonouredError)
    stubXhr(403, new Uint8Array())
    expect(() => xhrReadRange(URL_A, 10, 4)).toThrow('Range request returned status 403')
    expect(() => xhrReadRange(URL_A, 10, 4)).not.toThrow(RangeNotHonouredError)
  })
})

describe('HttpRangeFile', () => {
  it('reads relative to the member offset and reports failures as expired sources', () => {
    const { transport, requests, controls } = memoryTransport({ [URL_A]: ARTIFACT })
    const file = new HttpRangeFile('m', URL_A, MEMBER_OFFSET, MEMBER_SIZE, transport.readRangeSync)

    expect(file.read(16384, 100)).toEqual(DB.slice(16384, 16484))
    expect(requests).toEqual([{ kind: 'range', url: URL_A, offset: MEMBER_OFFSET, length: 65536 }])

    controls.failingUrls.add(URL_A)
    expect(() => file.read(10 * 16384, 100)).toThrow(SnapshotSourceExpiredError)
  })

  it('fails every read without a request once the storage stops honouring Range', () => {
    const { transport, requests, controls } = memoryTransport({ [URL_A]: ARTIFACT })
    const file = new HttpRangeFile('m', URL_A, MEMBER_OFFSET, MEMBER_SIZE, transport.readRangeSync)
    file.read(0, 100)
    controls.ignoreRange = true

    expect(() => file.read(10 * 16384, 100)).toThrow(SnapshotRangeUnsupportedError)
    const issued = requests.length
    expect(() => file.read(5 * 16384, 100)).toThrow(/stopped honouring Range requests/)
    file.location = { url: 'https://bucket.test/artifact?sig=b' }
    expect(() => file.read(MEMBER_SIZE - 100, 100)).toThrow(SnapshotRangeUnsupportedError)
    expect(requests).toHaveLength(issued)
  })

  it('treats a range of the wrong length as not honoured, for good', () => {
    const readRangeSync = vi.fn((_source: SnapshotSourceLocation, offset: number, length: number) =>
      ARTIFACT.slice(offset, offset + length - 1),
    )
    const file = new HttpRangeFile('m', URL_A, MEMBER_OFFSET, MEMBER_SIZE, readRangeSync)

    expect(() => file.read(0, 100)).toThrow(SnapshotRangeUnsupportedError)
    expect(() => file.read(10 * 16384, 100)).toThrow(/returned 65535 of 65536 bytes/)
    expect(readRangeSync).toHaveBeenCalledOnce()
  })
})

describe('openRawSnapshot', () => {
  const engine = RangeSqliteEngine.load()

  it('opens a range source without downloading the member', async () => {
    const { transport, requests } = memoryTransport({ [URL_A]: ARTIFACT })
    const source = { kind: 'range', url: URL_A, offset: MEMBER_OFFSET, size: MEMBER_SIZE } as const

    const opened = await openRawSnapshot(
      await engine,
      transport,
      'm',
      source,
      DEFAULT_RAW_SNAPSHOT_OPTIONS,
    )

    expect(opened.transport).toBe('raw-range')
    expect(opened.database.exec('SELECT COUNT(*) FROM evals')[0]!.values).toEqual([[6]])
    expect(requests.every((request) => request.length < MEMBER_SIZE)).toBe(true)
    expect(requests[0]).toEqual({ kind: 'fetch', url: URL_A, offset: MEMBER_OFFSET, length: 65536 })
    expect(requests.slice(1).some((request) => request.offset === MEMBER_OFFSET)).toBe(false)
  })

  it('reads by range from a storage that honours Range with status 200', async () => {
    const { transport, requests, controls } = memoryTransport({ [URL_A]: ARTIFACT })
    controls.rangeWith200 = true
    const source = { kind: 'range', url: URL_A, offset: MEMBER_OFFSET, size: MEMBER_SIZE } as const

    const opened = await openRawSnapshot(
      await engine,
      transport,
      'm',
      source,
      DEFAULT_RAW_SNAPSHOT_OPTIONS,
    )

    expect(opened.transport).toBe('raw-range')
    expect(opened.database.exec('SELECT COUNT(*) FROM evals')[0]!.values).toEqual([[6]])
    expect(requests[0]).toEqual({ kind: 'fetch', url: URL_A, offset: MEMBER_OFFSET, length: 65536 })
    expect(requests.every((request) => request.length <= 4 * 65536)).toBe(true)
    expect(opened.rangeFile?.cache.stats.bytesFetched).toBeLessThan(MEMBER_SIZE)
  })

  it('rejects a range member in WAL mode from the probe alone', async () => {
    const wal = ARTIFACT.slice()
    wal.set([2, 2], MEMBER_OFFSET + 18)
    const { transport, requests } = memoryTransport({ [URL_A]: wal })
    const source = { kind: 'range', url: URL_A, offset: MEMBER_OFFSET, size: MEMBER_SIZE } as const

    await expect(
      openRawSnapshot(await engine, transport, 'm', source, DEFAULT_RAW_SNAPSHOT_OPTIONS),
    ).rejects.toThrow(/WAL/)
    expect(requests).toHaveLength(1)
  })

  it('falls back to one full download when the server ignores Range', async () => {
    const { transport, requests, controls } = memoryTransport({ [URL_A]: ARTIFACT })
    controls.ignoreRange = true
    const source = { kind: 'range', url: URL_A, offset: MEMBER_OFFSET, size: MEMBER_SIZE } as const

    const opened = await openRawSnapshot(
      await engine,
      transport,
      'm',
      source,
      DEFAULT_RAW_SNAPSHOT_OPTIONS,
    )

    expect(opened.transport).toBe('raw-full')
    expect(opened.rangeFile).toBeNull()
    expect(opened.database.exec('SELECT COUNT(*) FROM evals')[0]!.values).toEqual([[6]])
    expect(requests.map((request) => request.kind)).toEqual(['fetch', 'fetch'])
  })

  it('refuses the fallback when the member is above the size cap', async () => {
    const { transport, controls } = memoryTransport({ [URL_A]: ARTIFACT })
    controls.ignoreRange = true
    const source = { kind: 'range', url: URL_A, offset: MEMBER_OFFSET, size: MEMBER_SIZE } as const

    await expect(
      openRawSnapshot(await engine, transport, 'm', source, {
        ...DEFAULT_RAW_SNAPSHOT_OPTIONS,
        maxFullDownloadBytes: MEMBER_SIZE - 1,
      }),
    ).rejects.toBeInstanceOf(SnapshotSourceTooLargeError)
  })

  it('opens a raw buffer in memory and rejects a WAL buffer', async () => {
    const { transport } = memoryTransport({})
    const opened = await openRawSnapshot(
      await engine,
      transport,
      'm',
      { kind: 'raw', buffer: DB.slice().buffer },
      DEFAULT_RAW_SNAPSHOT_OPTIONS,
    )
    expect(opened.transport).toBe('raw-full')

    const wal = DB.slice()
    wal.set([2, 2], 18)
    await expect(
      openRawSnapshot(
        await engine,
        transport,
        'm',
        { kind: 'raw', buffer: wal.buffer },
        DEFAULT_RAW_SNAPSHOT_OPTIONS,
      ),
    ).rejects.toThrow(/WAL/)
  })
})
