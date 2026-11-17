import { afterEach, describe, expect, it, vi } from 'vitest'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import {
  SnapshotRangeUnsupportedError,
  SnapshotSourceExpiredError,
  SnapshotSourceTimeoutError,
} from '../snapshot-source/errors'
import {
  createSyncRangeReader,
  HttpRangeFile,
  probeSnapshotHeader,
  readSourceRange,
  SYNC_RANGE_TIMEOUT_MS,
  syncRangeTimeoutMs,
  xhrReadRange,
  type SnapshotTransport,
  type SyncReadRange,
} from '../snapshot-source/httpSource'
import { RangeSqliteEngine } from '../snapshot-source/RangeSqliteEngine'
import { indexTar, readFixtureTar } from './helpers/snapshotSources'

const ARTIFACT = readFixtureTar('g_raw_sdk_0_5_0')
const [MEMBER_OFFSET, MEMBER_SIZE] = indexTar(ARTIFACT)['exp.db']!
const DB = ARTIFACT.slice(MEMBER_OFFSET, MEMBER_OFFSET + MEMBER_SIZE)
const URL_A = 'https://bucket.test/artifact?sig=secret-1'
const CHUNK = 16 * 1024
// Members of multi-GiB model artifacts start beyond what 32-bit arithmetic holds.
const FAR_OFFSET = 2 ** 32 + 512

/** What a sync XHR throws once `timeout` has passed without an answer. */
const timeoutError = () =>
  new DOMException(
    `Failed to execute 'send' on 'XMLHttpRequest': timeout for ${URL_A}`,
    'TimeoutError',
  )

describe('sync range reads', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('set a timeout on every request, after open as XHR requires', () => {
    const calls: string[] = []
    class FakeXhr {
      status = 206
      response = new Uint8Array(4).buffer
      responseType = ''
      private limit = 0
      open() {
        calls.push('open')
      }
      set timeout(value: number) {
        calls.push(`timeout ${value}`)
        this.limit = value
      }
      get timeout() {
        return this.limit
      }
      setRequestHeader() {}
      send() {
        calls.push('send')
      }
      getAllResponseHeaders() {
        return ''
      }
    }
    vi.stubGlobal('XMLHttpRequest', FakeXhr)

    xhrReadRange(URL_A, 0, 4)

    expect(calls).toEqual(['open', `timeout ${syncRangeTimeoutMs(4)}`, 'send'])
    expect(SYNC_RANGE_TIMEOUT_MS).toBe(30_000)
  })

  it('allow a larger request the time it takes at 32 KiB/s on top of the base timeout', () => {
    const timeouts: number[] = []
    const reader = createSyncRangeReader((_location, headers, timeoutMs) => {
      timeouts.push(timeoutMs)
      const [, start, end] = /^bytes=(\d+)-(\d+)$/.exec(headers.Range!)!.map(Number)
      return {
        status: 206,
        url: URL_A,
        contentRange: null,
        body: new Uint8Array(end! - start! + 1),
      }
    })
    reader({ url: URL_A, headers: {} }, 0, 64 * 1024)
    reader({ url: URL_A, headers: {} }, 0, 4 * 1024 * 1024)

    expect(timeouts).toEqual([32_000, 158_000])
  })

  it('report a timeout as timed-out, not as an expired URL, and read again afterwards', () => {
    let hang = true
    const lengths: number[] = []
    const read: SyncReadRange = (_location, offset, length) => {
      lengths.push(length)
      if (hang) throw timeoutError()
      return ARTIFACT.slice(offset, offset + length)
    }
    const file = new HttpRangeFile('m', URL_A, MEMBER_OFFSET, MEMBER_SIZE, read)

    let error: unknown
    try {
      file.read(0, 100)
    } catch (thrown) {
      error = thrown
    }
    expect(error).toBeInstanceOf(SnapshotSourceTimeoutError)
    expect(error).toMatchObject({
      code: 'timed-out',
      modelId: 'm',
      limit: syncRangeTimeoutMs(lengths[0]!),
    })
    expect((error as Error).message).not.toContain('secret')
    expect(file.failure).toBeNull()
    hang = false
    expect(file.read(0, 100)).toEqual(DB.slice(0, 100))
  })

  it('address a member beyond 4 GiB with exact offsets and Range headers', () => {
    const ranges: string[] = []
    const reader = createSyncRangeReader((_location, headers) => {
      ranges.push(headers.Range!)
      const [, start, end] = /^bytes=(\d+)-(\d+)$/.exec(headers.Range!)!.map(Number)
      return {
        status: 206,
        url: URL_A,
        contentRange: `bytes ${start}-${end}/${FAR_OFFSET + MEMBER_SIZE}`,
        body: DB.slice(start! - FAR_OFFSET, end! - FAR_OFFSET + 1),
      }
    })
    const file = new HttpRangeFile('m', URL_A, FAR_OFFSET, MEMBER_SIZE, reader, {
      chunkSize: CHUNK,
    })

    expect(file.read(CHUNK + 10, 20)).toEqual(DB.slice(CHUNK + 10, CHUNK + 30))
    expect(ranges).toEqual([`bytes=${FAR_OFFSET + CHUNK}-${FAR_OFFSET + 2 * CHUNK - 1}`])
    expect(ranges[0]).toBe('bytes=4294984192-4295000575')
  })

  it('fail a 416 mid-session as a failed request whose message holds no URL', () => {
    const reader = createSyncRangeReader(() => ({
      status: 416,
      url: URL_A,
      contentRange: 'bytes */99',
      contentType: 'application/json',
      body: new Uint8Array(),
    }))
    const file = new HttpRangeFile('m', URL_A, MEMBER_OFFSET, MEMBER_SIZE, reader)

    expect(() => file.read(0, 10)).toThrow(SnapshotSourceExpiredError)
    expect(() => file.read(0, 10)).toThrow(
      'Snapshot range read failed: Range request returned status 416',
    )
  })

  it('accept a gzip-encoded range only when the decoded body is the requested range', () => {
    const answer = (body: Uint8Array) =>
      createSyncRangeReader(() => ({ status: 206, url: URL_A, contentRange: null, body }))
    const exact = new HttpRangeFile(
      'm',
      URL_A,
      MEMBER_OFFSET,
      MEMBER_SIZE,
      answer(DB.slice(0, CHUNK)),
      {
        chunkSize: CHUNK,
      },
    )
    const longer = new HttpRangeFile(
      'm',
      URL_A,
      MEMBER_OFFSET,
      MEMBER_SIZE,
      answer(DB.slice(0, CHUNK + 7)),
      {
        chunkSize: CHUNK,
      },
    )

    expect(exact.read(0, 100)).toEqual(DB.slice(0, 100))
    expect(() => longer.read(0, 100)).toThrow(SnapshotRangeUnsupportedError)
    expect(longer.failure).toBeInstanceOf(SnapshotRangeUnsupportedError)
  })
})

describe('async range reads', () => {
  function fetchAnswering(response: (range: string) => Response) {
    const ranges: string[] = []
    const transport: SnapshotTransport = {
      fetch: async (_input, init) => {
        const range = new Headers(init?.headers).get('Range') ?? ''
        ranges.push(range)
        return response(range)
      },
      readRangeSync: () => new Uint8Array(),
    }
    return { transport, ranges }
  }

  it('probe a member beyond 4 GiB with an exact Range header', async () => {
    const { transport, ranges } = fetchAnswering(
      () => new Response(DB.slice(0, CHUNK), { status: 206 }),
    )

    const probe = await probeSnapshotHeader(transport, 'm', URL_A, FAR_OFFSET, MEMBER_SIZE, CHUNK)

    expect(probe).toEqual({ rangeIgnored: false, header: DB.slice(0, CHUNK) })
    expect(ranges).toEqual([`bytes=${FAR_OFFSET}-${FAR_OFFSET + CHUNK - 1}`])
  })

  it('fail a probe answered with 416 as a failed request whose message holds no URL', async () => {
    const { transport } = fetchAnswering(
      () =>
        new Response('{"error_code":"BAD_REQUEST"}', {
          status: 416,
          headers: { 'Content-Type': 'application/json', 'Content-Encoding': 'gzip' },
        }),
    )

    const probe = probeSnapshotHeader(transport, 'm', URL_A, MEMBER_OFFSET, MEMBER_SIZE, CHUNK)

    await expect(probe).rejects.toThrow(SnapshotSourceExpiredError)
    await expect(probe).rejects.toThrow(/^Snapshot header request returned status 416$/)
  })

  it('accept a gzip-encoded range only when the decoded body is the requested range', async () => {
    // Browsers decode the body; Content-Length still counts the encoded bytes.
    const gzipped = (body: Uint8Array) =>
      fetchAnswering(
        () =>
          new Response(body, {
            status: 206,
            headers: { 'Content-Encoding': 'gzip', 'Content-Length': '900' },
          }),
      ).transport

    expect(await readSourceRange(gzipped(DB.slice(0, CHUNK)), 'm', URL_A, 0, CHUNK)).toEqual(
      DB.slice(0, CHUNK),
    )
    expect(await readSourceRange(gzipped(DB.slice(0, CHUNK + 7)), 'm', URL_A, 0, CHUNK)).toBeNull()
  })
})

describe('an open that fails after the database was created', () => {
  const openFiles = (engine: RangeSqliteEngine) =>
    (engine as unknown as { open: Map<unknown, unknown> }).open

  it('closes the database and releases the file when the first query fails', async () => {
    const engine = await RangeSqliteEngine.load()
    const broken = {
      size: MEMBER_SIZE,
      read: () => {
        throw new Error('storage down')
      },
    }

    expect(() => engine.openDatabase(broken)).toThrow('storage down')
    expect(openFiles(engine).size).toBe(0)
  })

  it('closes the database and releases the file when reading the traits fails', async () => {
    const transport: SnapshotTransport = {
      fetch: async () => new Response(DB.slice(0, CHUNK), { status: 206 }),
      // The probe's chunk holds what opening reads; the traits need more.
      readRangeSync: () => {
        throw new Error('storage down')
      },
    }
    const provider = new ExperimentSnapshotDatabaseProvider({
      transport,
      raw: { cache: { chunkSize: CHUNK } },
    })
    const opened = vi.spyOn(RangeSqliteEngine.prototype, 'openDatabase')
    vi.spyOn(console, 'warn').mockImplementation(() => {})

    const failures = await provider.init({
      modelsInfo: [
        { modelId: 'm', source: { kind: 'range', url: URL_A, offset: 0, size: MEMBER_SIZE } },
      ],
    })

    expect(opened.mock.results.map((result) => result.type)).toEqual(['return'])
    expect(failures).toEqual([
      { modelId: 'm', error: expect.objectContaining({ code: 'snapshot-source-expired' }) },
    ])
    const engine = (provider as unknown as { engine: RangeSqliteEngine }).engine
    expect(openFiles(engine).size).toBe(0)
    vi.restoreAllMocks()
  })
})
