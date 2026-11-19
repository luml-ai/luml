import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import {
  ExperimentSnapshotDatabaseProvider,
  type ExperimentSnapshotModelSource,
  type SnapshotCallContext,
} from '../ExperimentSnapshotDatabaseProvider'
import { ExperimentSnapshotWorkerProxy } from '../ExperimentSnapshotWorkerProxy'
import { MetricBucketStore, type ChartState } from '../../metric-buckets/MetricBucketStore'
import { snapshotErrorFields } from '../snapshot-source/errors'
import type { SnapshotTransport } from '../snapshot-source/httpSource'
import {
  sameSourceLocation,
  toSourceLocation,
  type SnapshotSourceRef,
} from '../snapshot-source/sourceLocation'
import { browserLikeTransport } from './helpers/browserLikeTransport'
import { revision3Database } from './helpers/metricDatabases'
import { generatedMetrics } from './helpers/generatedMetrics'
import { FIXTURES_DIR, indexTar, readFixtureTar, writeTar } from './helpers/snapshotSources'
import {
  dataAnswers,
  issueLocation,
  newStorageState,
  respondAsStorage,
  sasQuery,
  STORAGE_PROFILES,
  type StorageOrigins,
  type StorageProfile,
  type StorageState,
} from './helpers/storageProfiles'

const ORIGINS: StorageOrigins = { page: 'http://viewer.test', storage: 'http://storage.test' }
const FIXTURE = 'h_raw_model_sdk_0_5_0'
const ARTIFACT = readFixtureTar(FIXTURE)
const MEMBER: string = JSON.parse(
  readFileSync(resolve(FIXTURES_DIR, `${FIXTURE}.json`), 'utf-8'),
).snapshot_member
const [MEMBER_OFFSET, MEMBER_SIZE] = indexTar(ARTIFACT)[MEMBER]!
const CHUNK = 16 * 1024
const MODEL = 'model'
const traceParams = {
  limit: 10,
  sort_by: 'created_at' as const,
  order: 'desc' as const,
  search: '',
  filters: [],
}
const evalParams = {
  dataset_id: 'qa_set',
  sort_by: 'created_at' as const,
  order: 'asc' as const,
  search: '',
  filters: [],
}

/** The worker protocol of the platform's snapshot worker, run in process. */
class InProcessWorker extends EventTarget {
  private provider: ExperimentSnapshotDatabaseProvider | null = null
  /** Every message the worker posted, as the main thread received it. */
  readonly posted: unknown[] = []

  constructor(
    private readonly transport: SnapshotTransport,
    private readonly maxFullDownloadBytes: number,
  ) {
    super()
  }

  postMessage(message: unknown): void {
    void this.handle(structuredClone(message) as WorkerMessage)
  }

  terminate(): void {}

  private async handle(message: WorkerMessage): Promise<void> {
    const { type, payload, requestId } = message
    if (type === 'cancel') return
    // As the platform's worker reports it.
    const failuresVersion = type === 'call' ? this.provider?.readFailuresVersion : undefined
    const statusesChanged = () =>
      failuresVersion !== undefined && this.provider?.readFailuresVersion !== failuresVersion
        ? { statusesChanged: true }
        : {}
    try {
      let data: unknown
      if (type === 'init') {
        this.provider = new ExperimentSnapshotDatabaseProvider({
          transport: this.transport,
          raw: { cache: { chunkSize: CHUNK }, maxFullDownloadBytes: this.maxFullDownloadBytes },
        })
        data = await this.provider.init({ modelsInfo: payload as ExperimentSnapshotModelSource[] })
      } else if (type === 'reopen') {
        const { modelId, source } = payload as { modelId: string; source: SnapshotSourceRef }
        data = await this.provider!.reopenSnapshot(modelId, source)
      } else {
        const { method, args } = payload as { method: string; args?: unknown[] }
        const target = this.provider as unknown as Record<string, (...values: unknown[]) => unknown>
        const context = { ...message.context, deadline: message.deadline }
        data = await this.provider!.runCall(context, () =>
          target[method]!.apply(this.provider, args ?? []),
        )
      }
      this.post({ type: 'result', requestId, data, ...statusesChanged() })
    } catch (error) {
      this.post({
        type: 'error',
        requestId,
        error: (error as Error).message,
        ...snapshotErrorFields(error),
        ...statusesChanged(),
      })
    }
  }

  private post(data: unknown): void {
    this.posted.push(structuredClone(data))
    this.dispatchEvent(new MessageEvent('message', { data: structuredClone(data) }))
  }
}

interface WorkerMessage {
  type: 'init' | 'call' | 'reopen' | 'cancel'
  payload: unknown
  requestId: string
  deadline?: number
  context?: SnapshotCallContext
}

/**
 * Hands out one location per credential generation, as the platform's URL cache does; the
 * credential of generation n is `base + n`.
 */
function locationIssuer(profile: StorageProfile, artifact = FIXTURE, base = 0) {
  let signs = 0
  const next = () => issueLocation(profile, ORIGINS, artifact, String(base + ++signs))
  let current: SnapshotSourceRef = next()
  return {
    get signs() {
      return signs
    },
    get: async () => current,
    renew: async (_modelId: string, failed: SnapshotSourceRef) => {
      if (sameSourceLocation(failed, current)) current = next()
      return current
    },
  }
}

interface Session {
  state: StorageState
  proxy: ExperimentSnapshotWorkerProxy
  issuer: ReturnType<typeof locationIssuer>
}

function session(profile: StorageProfile, maxFullDownloadBytes = 1024 * 1024 * 1024): Session {
  const state = newStorageState()
  const transport = browserLikeTransport(
    (request) =>
      respondAsStorage(request, {
        origins: ORIGINS,
        state,
        object: (name) => (name === FIXTURE ? ARTIFACT : undefined),
      }),
    ORIGINS,
  )
  const issuer = locationIssuer(profile)
  const proxy = new ExperimentSnapshotWorkerProxy(
    new InProcessWorker(transport, maxFullDownloadBytes) as unknown as Worker,
    { sourceUrls: issuer },
  )
  return { state, proxy, issuer }
}

async function open(current: Session) {
  const location = toSourceLocation(await current.issuer.get())
  const source = { kind: 'range' as const, ...location, offset: MEMBER_OFFSET, size: MEMBER_SIZE }
  return current.proxy.init([{ modelId: MODEL, source }])
}

function answers(state: StorageState, from = 0) {
  return dataAnswers(state.log.slice(from))
}

function preflights(state: StorageState) {
  return state.log.filter((entry) => entry.method === 'OPTIONS')
}

async function rejection(promise: Promise<unknown>) {
  try {
    await promise
  } catch (error) {
    return error
  }
  throw new Error('expected a rejection')
}

const byExpectation = (expected: StorageProfile['expected']) =>
  STORAGE_PROFILES.filter((profile) => profile.expected === expected)

describe.each(byExpectation('raw-range'))('$name storage, read by range', (profile) => {
  let current: Session

  beforeEach(async () => {
    current = session(profile)
    await open(current)
  })

  it('opens with one probe and sends only the headers the storage asked for', async () => {
    const [status] = await current.proxy.getExperimentStatuses()
    expect(status).toMatchObject({ transport: 'raw-range', transportFallback: null })
    const [stats] = await current.proxy.getTransportStats()
    const opened = answers(current.state)
    expect(opened[0]).toMatchObject({
      range: `bytes=${MEMBER_OFFSET}-${MEMBER_OFFSET + CHUNK - 1}`,
    })
    expect(opened).toHaveLength(1 + stats!.requests)
    const expectedHeaders = profile.auth === 'bearer' ? ['authorization'] : []
    const firstHop = current.state.log.filter((entry) => entry.method === 'GET')[0]
    expect(firstHop?.extraHeaders).toEqual(expectedHeaders)
    const crossOrigin = profile.host === 'storage'
    expect(preflights(current.state)).toHaveLength(crossOrigin && profile.auth === 'bearer' ? 1 : 0)
  })

  it('reads the catalog and a multi-chunk set of traces and evals', async () => {
    const [catalog] = await current.proxy.getMetricCatalogs()
    expect(catalog).toMatchObject({ modelId: MODEL, ok: true })
    const traces = await current.proxy.getAllTraces(traceParams)
    const evals = await current.proxy.getAllDatasetEvals(evalParams)

    expect(traces.length).toBeGreaterThan(0)
    expect(evals.length).toBeGreaterThan(0)
    const [stats] = await current.proxy.getTransportStats()
    expect(stats!.cacheMisses).toBeGreaterThanOrEqual(2)
    const reads = answers(current.state)
    expect(reads.length).toBe(1 + stats!.requests)
    expect(reads.every((entry) => entry.status === (profile.rangeAnswer === 200 ? 200 : 206))).toBe(
      true,
    )
    expect(reads.every((entry) => entry.bytes < MEMBER_SIZE)).toBe(true)
  })

  it('renews an expired source once and succeeds', async () => {
    current.state.revoked.add('1')
    const before = current.state.log.length

    const traces = await current.proxy.getAllTraces(traceParams)

    expect(traces.length).toBeGreaterThan(0)
    const later = answers(current.state, before)
    expect(later.filter((entry) => entry.status === profile.expired.status)).toHaveLength(1)
    expect(later.slice(1).every((entry) => entry.credential === '2')).toBe(true)
    expect(current.issuer.signs).toBe(2)
  })

  it('surfaces a permanent failure as an expired source without looping', async () => {
    current.state.rejectAll = true
    const before = current.state.log.length

    const error = await rejection(current.proxy.getAllTraces(traceParams))

    expect(error).toMatchObject({ code: 'snapshot-source-expired', modelId: MODEL })
    expect(answers(current.state, before).map((entry) => entry.status)).toEqual([
      profile.expired.status,
      profile.expired.status,
    ])
    expect(current.issuer.signs).toBe(2)
  })

  it.runIf(profile.rangeMayStop)(
    'fails for good after one whole-object answer when Range stops being honoured',
    async () => {
      current.state.ignoreRange = true
      const before = current.state.log.length

      for (const read of [
        () => current.proxy.getAllTraces(traceParams),
        () => current.proxy.getAllDatasetEvals(evalParams),
      ]) {
        expect(await rejection(read())).toMatchObject({ code: 'snapshot-range-unsupported' })
      }
      expect(answers(current.state, before).map((entry) => entry.bytes)).toEqual([ARTIFACT.length])
      expect(current.issuer.signs).toBe(1)
    },
  )
})

describe.each(byExpectation('raw-full'))('$name storage, loaded whole', (profile) => {
  it('falls back to one full download and says why', async () => {
    const current = session(profile)
    await open(current)

    expect(await current.proxy.getExperimentStatuses()).toEqual([
      expect.objectContaining({ transport: 'raw-full', transportFallback: 'range-ignored' }),
    ])
    expect((await current.proxy.getAllTraces(traceParams)).length).toBeGreaterThan(0)
    expect((await current.proxy.getMetricCatalogs())[0]).toMatchObject({ ok: true })
    expect(answers(current.state).map((entry) => [entry.status, entry.range !== null])).toEqual([
      [200, true],
      [200, false],
    ])
  })

  it('renews a source that expired before open once', async () => {
    const current = session(profile)
    current.state.revoked.add('1')

    await open(current)

    expect(answers(current.state).map((entry) => [entry.status, entry.credential])).toEqual([
      [profile.expired.status, '1'],
      [200, '2'],
      [200, '2'],
    ])
    expect(current.issuer.signs).toBe(2)
  })

  it('refuses a member above the full-download cap with a typed error after the probe', async () => {
    const current = session(profile, MEMBER_SIZE - 1)
    await open(current)

    const [status] = await current.proxy.getExperimentStatuses()
    expect(status?.error).toEqual({
      code: 'snapshot-source-too-large',
      message: expect.stringContaining(
        `is ${MEMBER_SIZE} bytes; full downloads are limited to ${MEMBER_SIZE - 1}`,
      ),
    })
    expect(answers(current.state)).toHaveLength(1)
    expect(current.issuer.signs).toBe(1)
  })

  it('surfaces a permanent failure without looping', async () => {
    const current = session(profile)
    current.state.rejectAll = true
    await open(current)

    const [status] = await current.proxy.getExperimentStatuses()
    expect(status?.error).toMatchObject({ code: 'snapshot-source-expired' })
    expect(answers(current.state)).toHaveLength(2)
    expect(current.issuer.signs).toBe(2)
  })
})

describe.each(byExpectation('redirect-error'))('$name storage', (profile) => {
  it('fails with a typed redirect error, without renewing a token the redirect drops', async () => {
    const current = session(profile)
    await open(current)

    const [status] = await current.proxy.getExperimentStatuses()
    expect(status?.error).toMatchObject({ code: 'snapshot-source-redirect' })
    expect(current.state.log.filter((entry) => entry.method === 'GET')).toEqual([
      expect.objectContaining({ host: 'page', status: 307, extraHeaders: ['authorization'] }),
      expect.objectContaining({ host: 'storage', status: 401, extraHeaders: [] }),
    ])
    expect(current.issuer.signs).toBe(1)
  })
})

describe.each(byExpectation('network-error'))('$name storage', (profile) => {
  it('fails to open with a clean error after one renewal, never looping', async () => {
    const current = session(profile)
    const logged: string[] = []
    vi.spyOn(console, 'warn').mockImplementation((...args: unknown[]) => {
      logged.push(args.map(String).join(' '))
    })

    await open(current)
    const [status] = await current.proxy.getExperimentStatuses()
    const traces = await current.proxy.getAllTraces(traceParams)
    const catalogs = await current.proxy.getMetricCatalogs()
    vi.restoreAllMocks()

    expect(status?.error).toEqual({
      code: 'snapshot-source-expired',
      message: 'Snapshot request failed: TypeError',
    })
    expect(traces).toEqual([])
    expect(catalogs).toEqual([{ modelId: MODEL, ok: false, error: status?.error }])
    expect(current.issuer.signs).toBe(2)
    expect(current.state.log.map((entry) => [entry.method, entry.credential])).toEqual([
      ['GET', '1'],
      ['GET', '2'],
    ])
    for (const text of logged) {
      expect(text).not.toMatch(/sig=|\/o\//)
    }
  })
})

describe('storage that cuts a range transfer short in the middle of the file', () => {
  const profile = STORAGE_PROFILES.find((item) => item.name === 'azure')!

  it('rejects a 206 with fewer bytes than asked for instead of reading zero-filled pages', async () => {
    const current = session(profile)
    await open(current)
    current.state.truncateFrom = MEMBER_OFFSET + CHUNK
    const before = current.state.log.length

    const first = await rejection(current.proxy.getAllTraces(traceParams))
    const second = await rejection(current.proxy.getAllDatasetEvals(evalParams))

    for (const error of [first, second]) {
      expect(error).toMatchObject({ code: 'snapshot-range-unsupported', modelId: MODEL })
    }
    expect(answers(current.state, before)).toHaveLength(1)
    expect(current.issuer.signs).toBe(1)
  })

  it('treats a dropped connection as a failed request: renews once, then surfaces it', async () => {
    const current = session(profile)
    await open(current)
    current.state.truncateFrom = MEMBER_OFFSET + CHUNK
    current.state.truncation = 'dropped'
    const before = current.state.log.length

    const error = await rejection(current.proxy.getAllTraces(traceParams))

    expect(error).toMatchObject({ code: 'snapshot-source-expired', modelId: MODEL })
    expect(answers(current.state, before)).toHaveLength(2)
    expect(current.issuer.signs).toBe(2)
  })
})

describe('a storage that accepts a range request and never answers', () => {
  it('times out that read without renewing the URL, and the worker reads on afterwards', async () => {
    const profile = STORAGE_PROFILES.find((item) => item.name === 's3')!
    const state = newStorageState()
    const transport = browserLikeTransport(
      (request) =>
        respondAsStorage(request, {
          origins: ORIGINS,
          state,
          object: (name) => (name === FIXTURE ? ARTIFACT : undefined),
        }),
      ORIGINS,
    )
    let hung = false
    const hanging: SnapshotTransport = {
      fetch: transport.fetch,
      readRangeSync: (location, offset, length) => {
        // What a sync XHR throws once its timeout passed; its message names the URL.
        if (hung) {
          throw new DOMException(`Timeout while loading '${location.url}'`, 'TimeoutError')
        }
        return transport.readRangeSync(location, offset, length)
      },
    }
    const issuer = locationIssuer(profile)
    const worker = new InProcessWorker(hanging, 1024 * 1024 * 1024)
    const proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker, {
      sourceUrls: issuer,
    })
    await open({ state, proxy, issuer })
    hung = true

    const error = await rejection(proxy.getAllTraces(traceParams))

    expect(error).toMatchObject({ code: 'timed-out', modelId: MODEL })
    expect(String((error as Error).message)).not.toMatch(/sig=|\/o\//)
    expect(issuer.signs).toBe(1)
    hung = false
    expect((await proxy.getAllTraces(traceParams)).length).toBeGreaterThan(0)
    expect((await proxy.getExperimentStatuses())[0]?.error).toBeNull()
  })
})

describe('Azure SAS URLs', () => {
  it('are refused by the emulated storage when the query is re-encoded', async () => {
    const profile = STORAGE_PROFILES.find((item) => item.name === 'azure-sas')!
    const state = newStorageState()
    const issued = String(issueLocation(profile, ORIGINS, FIXTURE, '1'))
    const reencoded = issued.replace(sasQuery('1'), decodeURIComponent(sasQuery('1')))
    const transport = browserLikeTransport(
      (request) => respondAsStorage(request, { origins: ORIGINS, state, object: () => ARTIFACT }),
      ORIGINS,
    )

    expect(transport.readRangeSync({ url: issued }, 0, 10)).toHaveLength(10)
    expect(() => transport.readRangeSync({ url: reencoded }, 0, 10)).toThrow(/status 403/)
  })
})

interface StoredObject {
  bytes: Uint8Array
  member: string
}

interface ModelSpec {
  modelId: string
  profile: StorageProfile
  artifact: string
  /** Credentials of this model's issuer are `base + n`. */
  base?: number
}

/** Several experiments, each with its own storage profile, artifact and URL issuer. */
function multiSession(
  models: ModelSpec[],
  objects: Map<string, StoredObject>,
  maxFullDownloadBytes = 1024 * 1024 * 1024,
) {
  const state = newStorageState()
  const transport = browserLikeTransport(
    (request) =>
      respondAsStorage(request, {
        origins: ORIGINS,
        state,
        object: (name) => objects.get(name)?.bytes,
      }),
    ORIGINS,
  )
  const issuers = new Map(
    models.map(({ modelId, profile, artifact, base }) => [
      modelId,
      locationIssuer(profile, artifact, base ?? 0),
    ]),
  )
  const issuerOf = (modelId: string) => {
    const issuer = issuers.get(modelId)
    if (!issuer) throw new Error(`no issuer for ${modelId}`)
    return issuer
  }
  const worker = new InProcessWorker(transport, maxFullDownloadBytes)
  const proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker, {
    sourceUrls: {
      get: (modelId) => issuerOf(modelId).get(),
      renew: (modelId, failed) => issuerOf(modelId).renew(modelId, failed),
    },
  })
  const open = async () => {
    const payload = await Promise.all(
      models.map(async ({ modelId, artifact }) => {
        const stored = objects.get(artifact)!
        const [offset, size] = indexTar(stored.bytes)[stored.member]!
        const location = toSourceLocation(await issuerOf(modelId).get())
        return { modelId, source: { kind: 'range' as const, ...location, offset, size } }
      }),
    )
    return proxy.init(payload)
  }
  return { state, proxy, worker, issuerOf, open }
}

const fixtureObject = (bytes = ARTIFACT): StoredObject => ({ bytes, member: MEMBER })

function corruptedFixture(): Uint8Array {
  const bytes = ARTIFACT.slice()
  bytes.fill(0, MEMBER_OFFSET, MEMBER_OFFSET + 16)
  return bytes
}

const byName = (name: string) => STORAGE_PROFILES.find((item) => item.name === name)!

describe('opening several experiments when one of them cannot open', () => {
  const s3 = byName('s3')
  const healthy = (modelId: string, artifact: string): ModelSpec => ({
    modelId,
    profile: s3,
    artifact,
  })

  async function futureSnapshot(): Promise<StoredObject> {
    const db = await revision3Database(generatedMetrics(3), { minReaderRevision: 5 })
    return { bytes: writeTar([{ name: 'exp.db', data: db }]), member: 'exp.db' }
  }

  const cases: {
    name: string
    middle: () => Promise<{ spec: ModelSpec; object: StoredObject }>
    code: string
    maxFull?: number
    revoke?: string[]
    /** Null when the middle one opens (and is refused later), so its reads vary. */
    middleAnswers: number | null
  }[] = [
    {
      name: 'too large for the full-download fallback',
      middle: async () => ({
        spec: { modelId: 'b', profile: byName('proxy-buffering'), artifact: 'fb' },
        object: fixtureObject(),
      }),
      code: 'snapshot-source-too-large',
      maxFull: MEMBER_SIZE - 1,
      middleAnswers: 1,
    },
    {
      name: 'not a valid snapshot',
      middle: async () => ({
        spec: { modelId: 'b', profile: s3, artifact: 'fb' },
        object: fixtureObject(corruptedFixture()),
      }),
      code: 'snapshot-format',
      middleAnswers: 1,
    },
    {
      name: 'written for a newer viewer',
      middle: async () => ({
        spec: { modelId: 'b', profile: s3, artifact: 'fb' },
        object: await futureSnapshot(),
      }),
      code: 'needs-newer-reader',
      middleAnswers: null,
    },
    {
      name: 'failing again after its one renewal',
      middle: async () => ({
        spec: { modelId: 'b', profile: s3, artifact: 'fb', base: 500 },
        object: fixtureObject(),
      }),
      code: 'snapshot-source-expired',
      revoke: ['501', '502'],
      middleAnswers: 2,
    },
  ]

  it.each(cases)('$name: the others open, nothing is probed twice', async (item) => {
    const { spec, object } = await item.middle()
    const objects = new Map([
      ['fa', fixtureObject()],
      ['fb', object],
      ['fc', fixtureObject()],
    ])
    const current = multiSession(
      [healthy('a', 'fa'), spec, healthy('c', 'fc')],
      objects,
      item.maxFull,
    )
    for (const credential of item.revoke ?? []) current.state.revoked.add(credential)

    await current.open()

    const statuses = await current.proxy.getExperimentStatuses()
    expect(statuses.map((status) => [status.modelId, status.error?.code ?? null])).toEqual([
      ['a', null],
      ['b', item.code],
      ['c', null],
    ])
    const opened = (artifact: string) =>
      dataAnswers(current.state.log).filter((entry) => entry.artifact === artifact)
    const alone = multiSession([healthy('a', 'fa')], objects)
    await alone.open()
    const openCost = dataAnswers(alone.state.log).length
    expect(opened('fa')).toHaveLength(openCost)
    expect(opened('fc')).toHaveLength(openCost)
    if (item.middleAnswers !== null) expect(opened('fb')).toHaveLength(item.middleAnswers)
    expect(current.issuerOf('a').signs).toBe(1)
    expect(current.issuerOf('c').signs).toBe(1)

    const catalogs = await current.proxy.getMetricCatalogs()
    expect(catalogs.map((result) => [result.modelId, result.ok])).toEqual([
      ['a', true],
      ['b', false],
      ['c', true],
    ])
    const traces = await current.proxy.getAllTraces(traceParams)
    const aloneTraces = await alone.proxy.getAllTraces(traceParams)
    expect(traces).toHaveLength(2 * aloneTraces.length)
    expect(aloneTraces.length).toBeGreaterThan(0)
  })

  it('reopens a renewed experiment without touching the open ones', async () => {
    const objects = new Map([
      ['fa', fixtureObject()],
      ['fb', fixtureObject()],
      ['fc', fixtureObject()],
    ])
    const current = multiSession(
      [healthy('a', 'fa'), { ...healthy('b', 'fb'), base: 500 }, healthy('c', 'fc')],
      objects,
    )
    current.state.revoked.add('501')

    await current.open()

    const statuses = await current.proxy.getExperimentStatuses()
    expect(statuses.every((status) => status.error === null)).toBe(true)
    const answered = dataAnswers(current.state.log)
    const alone = multiSession([healthy('a', 'fa')], objects)
    await alone.open()
    const openCost = dataAnswers(alone.state.log).length
    expect(answered.filter((entry) => entry.artifact === 'fa')).toHaveLength(openCost)
    expect(answered.filter((entry) => entry.artifact === 'fc')).toHaveLength(openCost)
    expect(
      answered.filter((entry) => entry.artifact === 'fb').map((entry) => entry.credential),
    ).toEqual(['501', ...Array.from({ length: openCost }, () => '502')])
  })
})

describe('URLs that age while experiments are open', () => {
  const s3 = byName('s3')
  const age = async (issuer: ReturnType<typeof locationIssuer>) => {
    await issuer.renew(MODEL, await issuer.get())
  }
  const outcome = (promise: Promise<unknown>) =>
    promise.then(
      () => 'ok',
      (error: Error) => error.message,
    )

  it('an experiment loaded in full reads on without a request or an error', async () => {
    const profile = byExpectation('raw-full')[0]!
    const current = session(profile)
    await open(current)
    const opened = current.state.log.length
    await age(current.issuer)

    const reads = [
      await outcome(current.proxy.getMetricCatalogs()),
      await outcome(current.proxy.getAllTraces(traceParams)),
    ]
    await age(current.issuer)
    reads.push(await outcome(current.proxy.getUniqueDatasetsIds()))

    expect(reads).toEqual(['ok', 'ok', 'ok'])
    expect(current.state.log.length).toBe(opened)
  })

  function comparisonWithFailedMember() {
    const objects = new Map([
      ['fa', fixtureObject()],
      ['fb', fixtureObject()],
    ])
    const current = multiSession(
      [
        { modelId: 'a', profile: s3, artifact: 'fa' },
        { modelId: 'b', profile: s3, artifact: 'fb', base: 500 },
      ],
      objects,
    )
    current.state.revoked.add('501')
    current.state.revoked.add('502')
    return current
  }

  it('a failing URL lookup of the member that did not open leaves the others alone', async () => {
    const current = comparisonWithFailedMember()
    await current.open()
    const failedIssuer = current.issuerOf('b')
    failedIssuer.get = async () => {
      throw new Error('Request failed with status 404')
    }

    const reads = [
      await outcome(current.proxy.getMetricCatalogs({ modelIds: ['a'] })),
      await outcome(current.proxy.getMetricCatalogs({ modelIds: ['a'] })),
      await outcome(current.proxy.getAllTraces(traceParams)),
    ]

    expect(reads).toEqual(['ok', 'ok', 'ok'])
  })

  it('a renewed URL of the member that did not open is not sent', async () => {
    const current = comparisonWithFailedMember()
    await current.open()
    await age(current.issuerOf('b'))

    expect(await outcome(current.proxy.getMetricCatalogs({ modelIds: ['a'] }))).toBe('ok')
    const statuses = await current.proxy.getExperimentStatuses()
    expect(statuses.map((status) => [status.modelId, status.error?.code ?? null])).toEqual([
      ['a', null],
      ['b', 'snapshot-source-expired'],
    ])
  })
})

describe('a comparison member whose access is revoked after open', () => {
  const s3 = byName('s3')

  async function comparison(modelIds: string[]) {
    const objects = new Map(modelIds.map((modelId) => [modelId, fixtureObject()]))
    const current = multiSession(
      modelIds.map((modelId, index) => ({
        modelId,
        profile: s3,
        artifact: modelId,
        base: 100 * index,
      })),
      objects,
    )
    await current.open()
    return current
  }

  /** A read for the screen: every trace on one page, from the first one. */
  async function tracesOnScreen(current: ReturnType<typeof multiSession>) {
    await current.proxy.resetTracesRequestParams()
    return current.proxy.getTraces({ ...traceParams, limit: 100_000 })
  }

  it.each([[['a', 'b']], [['a', 'b', 'c']]])(
    'of %j: renews its URL once, then shows the others and reports it',
    async (modelIds) => {
      vi.spyOn(console, 'warn').mockImplementation(() => undefined)
      const current = await comparison(modelIds)
      const alone = await comparison(['a'])
      const tracesOfOne = (await alone.proxy.getAllTraces(traceParams)).length
      const datasetsOfOne = await alone.proxy.getUniqueDatasetsIds()
      const statusChanges = vi.fn()
      current.proxy.onStatusesChanged(statusChanges)
      // Every credential of b, the one it has and the ones a renewal would issue.
      for (const credential of ['101', '102', '103']) current.state.revoked.add(credential)

      const before = current.state.log.length
      const traces = await tracesOnScreen(current)
      // Renewed once; the retry that left it out did not ask its storage again.
      const answersOfB = dataAnswers(current.state.log.slice(before)).filter(
        (entry) => entry.artifact === 'b',
      )
      expect(answersOfB.map((entry) => entry.credential)).toEqual(['101', '102'])
      expect(current.issuerOf('b').signs).toBe(2)
      expect(statusChanges).toHaveBeenCalledOnce()
      const datasets = await current.proxy.getUniqueDatasetsIds()

      expect(traces).toHaveLength(tracesOfOne * (modelIds.length - 1))
      expect(datasets).toEqual(datasetsOfOne)
      // Still left out: the statuses did not change again.
      expect(statusChanges).toHaveBeenCalledOnce()
      const statuses = await current.proxy.getExperimentStatuses()
      expect(statuses.map((status) => [status.modelId, status.error?.code ?? null])).toEqual(
        modelIds.map((modelId) => [modelId, modelId === 'b' ? 'snapshot-source-expired' : null]),
      )
      vi.restoreAllMocks()
    },
  )

  it('rejects an export instead of leaving the member out, after one renewal', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const current = await comparison(['a', 'b'])
    for (const credential of ['101', '102', '103']) current.state.revoked.add(credential)

    const before = current.state.log.length
    const traces = await rejection(current.proxy.getAllTraces(traceParams))
    const answersOfB = dataAnswers(current.state.log.slice(before)).filter(
      (entry) => entry.artifact === 'b',
    )
    const evals = await rejection(current.proxy.getAllDatasetEvals(evalParams))

    for (const error of [traces, evals]) {
      expect(error).toMatchObject({ code: 'snapshot-source-expired', modelId: 'b' })
      expect(String((error as Error).message)).not.toMatch(/sig=|\/o\//)
    }
    expect(answersOfB.map((entry) => entry.credential)).toEqual(['101', '102'])
    const statuses = await current.proxy.getExperimentStatuses()
    expect(statuses.every((status) => status.error === null)).toBe(true)
    vi.restoreAllMocks()
  })

  it('reads the member again once its access is restored', async () => {
    vi.spyOn(console, 'warn').mockImplementation(() => undefined)
    const current = await comparison(['a', 'b'])
    const alone = await comparison(['a'])
    const tracesOfOne = (await alone.proxy.getAllTraces(traceParams)).length
    current.state.revoked.add('101')
    current.state.revoked.add('102')
    expect(await tracesOnScreen(current)).toHaveLength(tracesOfOne)
    const statusChanges = vi.fn()
    current.proxy.onStatusesChanged(statusChanges)

    current.state.revoked.clear()

    expect(await tracesOnScreen(current)).toHaveLength(2 * tracesOfOne)
    expect(statusChanges).toHaveBeenCalledOnce()
    expect(await current.proxy.getAllTraces(traceParams)).toHaveLength(2 * tracesOfOne)
    const statuses = await current.proxy.getExperimentStatuses()
    expect(statuses.every((status) => status.error === null)).toBe(true)
    vi.restoreAllMocks()
  })
})

describe('an abandoned open', () => {
  it('stops the full download it started', async () => {
    let pulled = 0
    let cancelled = false
    const transport: SnapshotTransport = {
      readRangeSync: () => new Uint8Array(0),
      fetch: async (_input, init) => {
        const signal = init?.signal
        const ranged = new Headers(init?.headers).has('Range')
        if (ranged) {
          return new Response(ARTIFACT, { status: 200, headers: { 'Content-Length': '1' } })
        }
        const body = new ReadableStream<Uint8Array>({
          async pull(controller) {
            await new Promise((resolve) => setTimeout(resolve, 1))
            if (signal?.aborted) {
              cancelled = true
              controller.error(signal.reason)
              return
            }
            pulled += 1024
            controller.enqueue(new Uint8Array(1024))
          },
          cancel() {
            cancelled = true
          },
        })
        return new Response(body, { status: 200 })
      },
    }
    const provider = new ExperimentSnapshotDatabaseProvider({ transport })
    const controller = new AbortController()
    const source = {
      kind: 'range' as const,
      url: 'http://storage.test/a?sig=1',
      offset: MEMBER_OFFSET,
      size: MEMBER_SIZE,
    }
    const opening = provider.init({ modelsInfo: [{ modelId: MODEL, source }] }, controller.signal)
    await vi.waitFor(() => expect(pulled).toBeGreaterThan(0))
    controller.abort()

    await expect(opening).rejects.toMatchObject({ name: 'AbortError' })
    await vi.waitFor(() => expect(cancelled).toBe(true))
    const stopped = pulled
    await new Promise((resolve) => setTimeout(resolve, 20))
    expect(pulled).toBe(stopped)
    expect(pulled).toBeLessThan(ARTIFACT.length)
  })
})

// Credentials of these sessions hold this marker, in the query and in the Authorization header.
const SECRET_BASE = 4_817_293_000
const SECRET = '4817293'

describe.each(STORAGE_PROFILES)('$name storage: secrets in errors', (profile) => {
  const modes: {
    name: string
    before?: (state: StorageState) => void
    after?: (state: StorageState) => void
    maxFull?: number
  }[] = [
    { name: 'expired before open', before: (state) => (state.rejectAll = true) },
    { name: 'expired while open', after: (state) => (state.rejectAll = true) },
    { name: 'Range stops while open', after: (state) => (state.ignoreRange = true) },
    {
      name: 'a short 206',
      after: (state) => {
        state.truncateFrom = MEMBER_OFFSET + CHUNK
      },
    },
    {
      name: 'a dropped connection',
      after: (state) => {
        state.truncateFrom = MEMBER_OFFSET + CHUNK
        state.truncation = 'dropped'
      },
    },
    { name: 'too large to load in full', maxFull: MEMBER_SIZE - 1 },
  ]

  let logged: string[] = []
  beforeEach(() => {
    logged = []
    for (const method of ['log', 'info', 'warn', 'error', 'debug'] as const) {
      vi.spyOn(console, method).mockImplementation((...args: unknown[]) => {
        logged.push(args.map(describeValue).join(' '))
      })
    }
  })
  afterEach(() => vi.restoreAllMocks())

  function describeValue(value: unknown): string {
    if (value instanceof Error) {
      return `${value.name}: ${value.message} ${JSON.stringify({ ...value })} ${String(value.cause ?? '')}`
    }
    return typeof value === 'string' ? value : JSON.stringify(value)
  }

  const settle = async () => {
    for (let round = 0; round < 5; round++) await new Promise((resolve) => setTimeout(resolve, 5))
  }

  it.each(modes)('$name: no message carries the URL or credential', async (mode) => {
    const objects = new Map([[FIXTURE, fixtureObject()]])
    const current = multiSession(
      [{ modelId: MODEL, profile, artifact: FIXTURE, base: SECRET_BASE }],
      objects,
      mode.maxFull,
    )
    const credential = String(SECRET_BASE + 1)
    expect(JSON.stringify(await current.issuerOf(MODEL).get())).toContain(credential)
    mode.before?.(current.state)
    const messages: string[] = []
    const failed = (error: unknown) => messages.push(describeValue(error))
    await current.open().catch(failed)

    const store = new MetricBucketStore(current.proxy, { debounceMs: 0 })
    const states: ChartState[] = []
    const chart = store.subscribe((state) => states.push(state))
    const catalogs = await store.loadCatalogs()
    const key = catalogs.catalogs.get(MODEL)?.metrics[0]?.key ?? 'train_loss'
    chart.request({ modelIds: [MODEL], keys: [key], bucketBudget: 100 })
    await settle()
    mode.after?.(current.state)
    await store.reload([MODEL]).catch(failed)
    await settle()
    await current.proxy.getAllTraces(traceParams).catch(failed)
    await current.proxy.getAllDatasetEvals(evalParams).catch(failed)
    await current.proxy.getDynamicMetricData(key).catch(failed)
    const statuses = await current.proxy.getExperimentStatuses()
    store.dispose()

    const chartErrors = states.flatMap((state) => state.errors.map((item) => item.error.message))
    const statusErrors = statuses.flatMap((status) => (status.error ? [status.error.message] : []))
    const catalogErrors = [...catalogs.errors.values()].map((error) => error.message)
    const shown = [...messages, ...chartErrors, ...statusErrors, ...catalogErrors]
    for (const text of [...shown, ...logged, ...current.worker.posted.map(describeValue)]) {
      expect(text).not.toContain(SECRET)
    }
    for (const text of [...shown, ...logged]) {
      // A query string or the object path; SQL text in SQLite errors holds bare `?` markers.
      expect(text).not.toMatch(/\?\S*=|\/o\//)
    }
  })
})
