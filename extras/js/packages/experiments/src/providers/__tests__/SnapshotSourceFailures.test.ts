import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import {
  isTransientSourceFailure,
  snapshotErrorFields,
  snapshotErrorFromFields,
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
import { DEFAULT_REQUEST_TIMEOUT_MS as METRIC_READ_DEADLINE_MS } from '../../metric-buckets/MetricBucketStore'
import { indexTar, memoryTransport, readFixtureTar } from './helpers/snapshotSources'

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
    expect(SYNC_RANGE_TIMEOUT_MS).toBe(25_000)
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

    expect(timeouts).toEqual([27_000, 153_000])
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

  it('free the worker from a stalled one-chunk read before a metric read gives up', () => {
    expect(syncRangeTimeoutMs(4 * CHUNK)).toBeLessThan(METRIC_READ_DEADLINE_MS)
  })

  describe('within the deadline of the call that needs them', () => {
    afterEach(() => vi.useRealTimers())

    function recordingFile(deadline: () => number) {
      const requests: { length: number; timeoutMs: number | undefined }[] = []
      const read: SyncReadRange = (_location, offset, length, timeoutMs) => {
        requests.push({ length, timeoutMs })
        return ARTIFACT.slice(offset, offset + length)
      }
      const file = new HttpRangeFile(
        'm',
        URL_A,
        MEMBER_OFFSET,
        MEMBER_SIZE,
        read,
        { chunkSize: CHUNK, maxReadAheadBytes: 64 * CHUNK },
        deadline,
      )
      return { file, requests }
    }

    function scan(file: HttpRangeFile, chunks: number) {
      for (let index = 0; index < chunks; index++) file.read(index * CHUNK, CHUNK)
    }

    it('never wait longer for one request than the call has left', () => {
      vi.useFakeTimers({ now: 1_000_000 })
      const { file, requests } = recordingFile(() => 1_000_000 + 5_000)

      file.read(0, 100)

      expect(requests).toEqual([{ length: CHUNK, timeoutMs: 5_000 }])
    })

    it('keep the full timeout of a request that fits, so a slow link still finishes', () => {
      vi.useFakeTimers({ now: 1_000_000 })
      const { file, requests } = recordingFile(() => 1_000_000 + 60_000)

      file.read(0, 100)

      expect(requests).toEqual([{ length: CHUNK, timeoutMs: syncRangeTimeoutMs(CHUNK) }])
    })

    /** A link of `bytesPerMs` after `latencyMs`; the clock moves as each request takes. */
    function linkFile(deadline: number, bytesPerMs: number, latencyMs: number) {
      const requests: { length: number; tookMs: number; timeoutMs: number }[] = []
      const read: SyncReadRange = (_location, _offset, length, timeoutMs) => {
        const tookMs = latencyMs + length / bytesPerMs
        requests.push({ length, tookMs, timeoutMs: timeoutMs! })
        vi.setSystemTime(Date.now() + tookMs)
        return new Uint8Array(length)
      }
      const size = 32 * 1024 * 1024
      return { file: new HttpRangeFile('m', URL_A, 0, size, read, {}, () => deadline), requests }
    }

    function scanBytes(file: HttpRangeFile, bytes: number) {
      for (let offset = 0; offset < bytes; offset += CHUNK) file.read(offset, CHUNK)
    }

    it.each([
      ['a fresh call', 60_000],
      ['a call half over', 30_000],
      ['a call without a deadline', Infinity],
    ])('read ahead on a fast link as far as without a deadline, in %s', (_name, timeLeft) => {
      vi.useFakeTimers({ now: 1_000_000 })
      const { file, requests } = linkFile(1_000_000 + timeLeft, 10_000, 20)

      scanBytes(file, 16 * 1024 * 1024)

      expect(requests).toHaveLength(10)
    })

    it('finish a scan on a slow link (62.5 KB/s) inside the deadline of a metric read', () => {
      vi.useFakeTimers({ now: 1_000_000 })
      const deadline = 1_000_000 + METRIC_READ_DEADLINE_MS
      const { file, requests } = linkFile(deadline, 62.5, 50)

      scanBytes(file, 1024 * 1024)

      expect(Date.now()).toBeLessThanOrEqual(deadline)
      for (const request of requests) expect(request.tookMs).toBeLessThan(request.timeoutMs)
      // Read-ahead still ramps up, within what the measured link carries in the time left.
      expect(requests).toHaveLength(5)
    })

    it('read only the chunks a read needs when no read-ahead fits', () => {
      vi.useFakeTimers({ now: 1_000_000 })
      const { file, requests } = recordingFile(() => 1_000_000 + 500)

      scan(file, 4)
      file.read(10 * CHUNK, 3 * CHUNK)

      expect(requests.map((request) => request.length)).toEqual([
        ...Array.from({ length: 4 }, () => CHUNK),
        3 * CHUNK,
      ])
    })

    it('send no request once the caller has given up', () => {
      vi.useFakeTimers({ now: 1_000_000 })
      const { file, requests } = recordingFile(() => 1_000_000)

      expect(() => file.read(0, 100)).toThrow(SnapshotSourceTimeoutError)
      expect(requests).toEqual([])
    })
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
    expect(() => file.read(0, 10)).toThrow(expect.objectContaining({ status: 416 }))
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
    await expect(probe).rejects.toMatchObject({ status: 416 })
  })

  it('fail a probe without an answer as a failed request without a status', async () => {
    const transport: SnapshotTransport = {
      fetch: async () => {
        throw new TypeError(`Failed to fetch ${URL_A}`)
      },
      readRangeSync: () => new Uint8Array(),
    }

    const failure = await probeSnapshotHeader(
      transport,
      'm',
      URL_A,
      MEMBER_OFFSET,
      MEMBER_SIZE,
      CHUNK,
    ).catch((error: unknown) => error)

    expect(failure).toBeInstanceOf(SnapshotSourceExpiredError)
    expect((failure as SnapshotSourceExpiredError).status).toBeUndefined()
    expect(isTransientSourceFailure(failure)).toBe(true)
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
    // A read that got no status is one the same URL may answer: the proxy may open it again.
    expect(failures).toEqual([
      {
        modelId: 'm',
        error: expect.objectContaining({ code: 'snapshot-source-expired' }),
        transient: true,
      },
    ])
    const engine = (provider as unknown as { engine: RangeSqliteEngine }).engine
    expect(openFiles(engine).size).toBe(0)
    vi.restoreAllMocks()
  })
})

describe('a failed source request sent again with the same URL', () => {
  it.each([
    [undefined, true],
    [0, true],
    [500, true],
    [503, true],
    [408, true],
    [429, true],
    [400, false],
    [403, false],
    [404, false],
    [416, false],
  ])('with status %s is transient: %s', (status, transient) => {
    expect(isTransientSourceFailure(new SnapshotSourceExpiredError('m', 'failed', status))).toBe(
      transient,
    )
  })

  it('is never retried for an error that is not a failed request', () => {
    expect(isTransientSourceFailure(new SnapshotSourceTimeoutError('m', 30_000))).toBe(false)
    expect(isTransientSourceFailure(new TypeError('Failed to fetch'))).toBe(false)
  })

  it('keeps its status across the worker boundary', () => {
    const fields = snapshotErrorFields(new SnapshotSourceExpiredError('m', 'failed', 503))

    expect(fields).toEqual({ code: 'snapshot-source-expired', modelId: 'm', status: 503 })
    expect(snapshotErrorFromFields(fields!, 'failed')).toMatchObject({ status: 503 })
  })
})

describe('a comparison member whose storage fails after open', () => {
  type Fault = 'denied' | 'range-ignored' | 'timeout'
  const urlOf = (modelId: string) => `https://bucket.test/${modelId}?sig=secret-${modelId}`
  const traceParams = { limit: 20, sort_by: 'created_at', order: 'desc', search: '', filters: [] }
  const evalPage = {
    dataset_id: 'qa_set',
    limit: 20,
    sort_by: 'created_at',
    order: 'asc',
    search: '',
    filters: [],
  } as const

  async function openMembers(modelIds: string[], broken: string) {
    const store = memoryTransport(Object.fromEntries(modelIds.map((id) => [urlOf(id), ARTIFACT])))
    const state: { fault: Fault | null } = { fault: null }
    const transport: SnapshotTransport = {
      ...store.transport,
      readRangeSync: (location, offset, length) => {
        if (location.url === urlOf(broken) && state.fault === 'range-ignored') {
          return ARTIFACT.slice()
        }
        if (location.url === urlOf(broken) && state.fault === 'timeout') throw timeoutError()
        return store.transport.readRangeSync(location, offset, length)
      },
    }
    const provider = new ExperimentSnapshotDatabaseProvider({ transport })
    const failures = await provider.init({
      modelsInfo: modelIds.map((modelId) => ({
        modelId,
        source: { kind: 'range', url: urlOf(modelId), offset: MEMBER_OFFSET, size: MEMBER_SIZE },
      })),
    })
    expect(failures).toEqual([])
    const breakStorage = (fault: Fault) => {
      state.fault = fault
      if (fault === 'denied') store.controls.failingUrls.add(urlOf(broken))
    }
    const repair = () => {
      state.fault = null
      store.controls.failingUrls.delete(urlOf(broken))
    }
    return { provider, breakStorage, repair }
  }

  const codeOf = (read: Promise<unknown>) =>
    read.then(
      () => 'read',
      (error: { code?: string }) => error.code ?? 'other',
    )

  async function readAll(provider: ExperimentSnapshotDatabaseProvider) {
    await provider.resetTracesRequestParams()
    await provider.resetEvalsDatasetsRequestParams()
    const catalogs = await provider.getMetricCatalogs()
    const evals = await provider.getNextEvalsByDatasetId(evalPage)
    const datasetId = evalPage.dataset_id
    return {
      catalogs: catalogs.map((item) => [item.modelId, item.ok]),
      datasets: await provider.getUniqueDatasetsIds(),
      evals: [...new Set(evals.map((row) => row.modelId))],
      columns: await provider.getEvalsColumns(datasetId),
      scores: (await provider.getDatasetAverageScores(datasetId)).map((item) => item.modelId),
      annotations: await codeOf(provider.getEvalsDatasetAnnotationsSummary(datasetId)),
      traces: (await provider.getTraces(traceParams)).length,
      // Exports: a file that silently misses an experiment is worse than an error.
      allTraces: await codeOf(provider.getAllTraces(traceParams)),
      allEvals: await codeOf(provider.getAllDatasetEvals(evalPage)),
    }
  }

  beforeEach(() => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
  })

  afterEach(() => vi.restoreAllMocks())

  it.each([
    ['denied', ['healthy', 'broken']],
    ['denied', ['first', 'broken', 'last']],
    ['range-ignored', ['healthy', 'broken']],
    ['range-ignored', ['first', 'broken', 'last']],
  ] as const)('%s, of %j: the others show, the member is reported', async (fault, members) => {
    const { provider, breakStorage } = await openMembers([...members], 'broken')
    const alone = await openMembers(['healthy'], 'none')
    const tracesOfOne = (await alone.provider.getAllTraces(traceParams)).length
    const datasetsOfOne = await alone.provider.getUniqueDatasetsIds()
    const columnsOfOne = await alone.provider.getEvalsColumns(evalPage.dataset_id)
    breakStorage(fault)

    const read = await readAll(provider)

    const healthy = members.filter((id) => id !== 'broken')
    const brokenCode = fault === 'denied' ? 'snapshot-source-expired' : 'snapshot-range-unsupported'
    expect(read).toEqual({
      catalogs: members.map((id) => [id, id !== 'broken']),
      datasets: datasetsOfOne,
      evals: healthy,
      columns: columnsOfOne,
      scores: healthy,
      annotations: 'read',
      traces: Math.min(traceParams.limit, tracesOfOne) * healthy.length,
      allTraces: brokenCode,
      allEvals: brokenCode,
    })
    const statuses = await provider.getExperimentStatuses()
    expect(statuses.map((status) => [status.modelId, status.error?.code ?? null])).toEqual(
      members.map((id) => [id, id === 'broken' ? brokenCode : null]),
    )
    expect(JSON.stringify(statuses)).not.toContain('secret')
  })

  it('reads the member again once its storage answers, from its first trace page', async () => {
    const { provider, breakStorage, repair } = await openMembers(['healthy', 'broken'], 'broken')
    const onePerPage = { ...traceParams, limit: 1 }
    breakStorage('denied')
    const without = await provider.getTraces(onePerPage)
    repair()

    const page = await provider.getTraces(onePerPage)

    // The healthy member's second page, and the first page of the member that was left out.
    expect(without).toHaveLength(1)
    expect(page).toHaveLength(2)
    expect(page.map((trace) => trace.trace_id)).toContain(without[0]!.trace_id)
    const statuses = await provider.getExperimentStatuses()
    expect(statuses.every((status) => status.error === null)).toBe(true)
  })

  it('forgets a member left out once it reads again, and tells the caller both times', async () => {
    const { provider, breakStorage, repair } = await openMembers(['healthy', 'broken'], 'broken')
    const versions = [provider.readFailuresVersion]
    breakStorage('denied')
    await provider.getUniqueDatasetsIds()
    versions.push(provider.readFailuresVersion)
    await provider.getUniqueDatasetsIds()
    versions.push(provider.readFailuresVersion)
    repair()

    await provider.getMetricCatalogs()
    versions.push(provider.readFailuresVersion)

    expect(versions).toEqual([0, 1, 1, 2])
    const statuses = await provider.getExperimentStatuses()
    expect(statuses.every((status) => status.error === null)).toBe(true)
  })

  it('keeps a member reported after a read from the cache, until a read reaches its storage', async () => {
    const { provider, breakStorage, repair } = await openMembers(['healthy', 'stalled'], 'stalled')
    const datasetsBefore = await provider.getUniqueDatasetsIds()
    const errorOf = async () =>
      (await provider.getExperimentStatuses()).find((status) => status.modelId === 'stalled')?.error
        ?.code ?? null
    breakStorage('timeout')
    const versions = [provider.readFailuresVersion]
    const tracesWithout = await provider.getTraces(traceParams)
    versions.push(provider.readFailuresVersion)

    const fromCache = await provider.getUniqueDatasetsIds()
    versions.push(provider.readFailuresVersion)
    const shownAfterCachedRead = await errorOf()
    repair()
    await provider.resetTracesRequestParams()
    const tracesWith = await provider.getTraces(traceParams)
    versions.push(provider.readFailuresVersion)
    await provider.getUniqueDatasetsIds()
    versions.push(provider.readFailuresVersion)

    expect(fromCache).toEqual(datasetsBefore)
    expect(shownAfterCachedRead).toBe('timed-out')
    expect(tracesWith.length).toBe(2 * tracesWithout.length)
    expect(versions).toEqual([0, 1, 1, 2, 2])
    expect(await errorOf()).toBeNull()
  })

  it('does not report a member whose read the deadline of the call stopped', async () => {
    const { provider } = await openMembers(['healthy', 'late'], 'none')
    const expired = { deadline: Date.now() - 1 }

    const catalogs = await provider.runCall(expired, () => provider.getMetricCatalogs())
    const datasets = provider.runCall(expired, () => provider.getUniqueDatasetsIds())

    expect(catalogs.map((item) => [item.modelId, item.ok])).toEqual([
      ['healthy', false],
      ['late', false],
    ])
    await expect(datasets).rejects.toMatchObject({ code: 'timed-out', callDeadline: true })
    const statuses = await provider.getExperimentStatuses()
    expect(statuses.every((status) => status.error === null)).toBe(true)
    expect(provider.readFailuresVersion).toBe(0)
  })

  it.each([27_000, 25_200])(
    'reports a member whose storage stalls with %s ms of the call left, and shows the others',
    async (timeLeftMs) => {
      const { provider, breakStorage } = await openMembers(['healthy', 'stalled'], 'stalled')
      const alone = await openMembers(['healthy'], 'none')
      const datasetsOfOne = await alone.provider.getUniqueDatasetsIds()
      const tracesOfOne = (await alone.provider.getTraces(traceParams)).length
      breakStorage('timeout')
      // More than the storage's base allowance, less than a large request's size allowance.
      const call = { deadline: Date.now() + timeLeftMs }

      const datasets = await provider.runCall(call, () => provider.getUniqueDatasetsIds())
      const traces = await provider.runCall(call, () => provider.getTraces(traceParams))

      expect(datasets).toEqual(datasetsOfOne)
      expect(traces.length).toBe(tracesOfOne)
      const statuses = await provider.getExperimentStatuses()
      expect(statuses.map((status) => [status.modelId, status.error?.code ?? null])).toEqual([
        ['healthy', null],
        ['stalled', 'timed-out'],
      ])
    },
  )

  it.each([
    ['a single experiment', ['only']],
    ['a comparison', ['healthy', 'only']],
  ])('drops the notice of %s once a timed-out read works again', async (_name, members) => {
    const { provider, breakStorage, repair } = await openMembers([...members], 'only')
    const errorOf = async () =>
      (await provider.getExperimentStatuses()).find((status) => status.modelId === 'only')?.error
    breakStorage('timeout')
    const [failed] = (await provider.getMetricCatalogs()).filter((item) => item.modelId === 'only')
    // Only a comparison leaves the experiment out and reports it; a single one shows the error.
    const shown = (await errorOf())?.code ?? null
    repair()

    const [read] = (await provider.getMetricCatalogs()).filter((item) => item.modelId === 'only')

    expect(failed).toMatchObject({ ok: false, error: { code: 'timed-out' } })
    expect(shown).toBe(members.length > 1 ? 'timed-out' : null)
    expect(read).toMatchObject({ ok: true })
    expect(await errorOf()).toBeNull()
  })

  it('still rejects the read of a single experiment', async () => {
    const { provider, breakStorage } = await openMembers(['only'], 'only')
    breakStorage('denied')

    await expect(provider.getUniqueDatasetsIds()).rejects.toBeInstanceOf(SnapshotSourceExpiredError)
    await expect(provider.getTraces(traceParams)).rejects.toBeInstanceOf(SnapshotSourceExpiredError)
    await expect(provider.getMetricCatalogs()).rejects.toBeInstanceOf(SnapshotSourceExpiredError)
  })

  it('still rejects a failure that is not the storage', async () => {
    const { provider } = await openMembers(['healthy', 'other'], 'other')

    await expect(
      provider.getTraces({ ...traceParams, filters: ['no_such_field = 1'] }),
    ).rejects.toThrow()
  })

  it('rethrows an expired source the caller renews, marked so that it can be left out', async () => {
    const { provider, breakStorage } = await openMembers(['healthy', 'broken'], 'broken')
    breakStorage('denied')
    const failedSources = [
      { modelId: 'broken', error: { code: 'snapshot-source-expired' as const, message: 'failed' } },
    ]

    const error = await provider
      .runCall({ renewableSources: ['healthy', 'broken'] }, () => provider.getUniqueDatasetsIds())
      .catch((caught: unknown) => caught)
    const leftOut = await provider.runCall({ failedSources }, () => provider.getUniqueDatasetsIds())

    expect(error).toMatchObject({ modelId: 'broken', isolatable: true })
    expect(snapshotErrorFields(error)).toMatchObject({ modelId: 'broken', isolatable: true })
    expect(leftOut.length).toBeGreaterThan(0)
    expect(leftOut).toEqual(await provider.getUniqueDatasetsIds())
  })
})

describe('a comparison member that failed at open', () => {
  const urlOf = (modelId: string) => `https://bucket.test/${modelId}?sig=secret-${modelId}`
  const traceParams = { sort_by: 'created_at', order: 'desc', search: '', filters: [] } as const
  const evalParams = {
    dataset_id: 'qa_set',
    sort_by: 'created_at',
    order: 'asc',
    search: '',
    filters: [],
  } as const

  async function openWithFailedMember() {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const store = memoryTransport({ [urlOf('healthy')]: ARTIFACT, [urlOf('broken')]: ARTIFACT })
    store.controls.failingUrls.add(urlOf('broken'))
    const provider = new ExperimentSnapshotDatabaseProvider({ transport: store.transport })
    const failures = await provider.init({
      modelsInfo: ['healthy', 'broken'].map((modelId) => ({
        modelId,
        source: { kind: 'range', url: urlOf(modelId), offset: MEMBER_OFFSET, size: MEMBER_SIZE },
      })),
    })
    expect(failures.map((failure) => failure.modelId)).toEqual(['broken'])
    return { provider, openError: failures[0]!.error }
  }

  afterEach(() => vi.restoreAllMocks())

  it('rejects both exports with its open error, so no file misses it', async () => {
    const { provider, openError } = await openWithFailedMember()

    await expect(provider.getAllTraces(traceParams)).rejects.toMatchObject(openError)
    await expect(provider.getAllDatasetEvals(evalParams)).rejects.toMatchObject(openError)
  })

  it('still shows the healthy member on screen', async () => {
    const { provider } = await openWithFailedMember()

    const evals = await provider.getNextEvalsByDatasetId({ ...evalParams, limit: 20 })
    const traces = await provider.getTraces({ ...traceParams, limit: 20 })

    expect(new Set(evals.map((row) => row.modelId))).toEqual(new Set(['healthy']))
    expect(traces.length).toBeGreaterThan(0)
  })
})
