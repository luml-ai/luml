import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { BucketCache } from '../BucketCache'
import {
  MetricBucketStore,
  type ChartState,
  type ChartSubscription,
  type MetricBucketSource,
  metricStepRange,
  metricStepRanges,
} from '../MetricBucketStore'
import type { BucketReadRequest } from '../planner'
import type {
  ExperimentMetricCatalog,
  ExperimentResult,
  ExperimentSnapshotStatus,
  MetricBucket,
  MetricBucketsRequest,
  MetricBucketsResponse,
  MetricCatalogEntry,
  MetricCatalogsRequest,
} from '../types'

const STEPS = 100_000
const DEBOUNCE = 50

const KEYS = ['loss', 'acc']

function catalogOf(lengths: (key: string) => number, keys = KEYS): ExperimentMetricCatalog {
  return {
    revision: 3,
    bucket_min_level: 3,
    bucket_max_level: 12,
    skipped_rows: 0,
    metrics: keys.map((key) => ({
      key,
      first_step: 0,
      last_step: lengths(key) - 1,
      count: lengths(key),
      min: 1,
      max: 1,
    })),
  }
}

/** Dense steps 0..total-1, every value 1. */
function denseBuckets(level: number, start: number, end: number, total = STEPS): MetricBucket[] {
  const width = 4 ** level
  const buckets: MetricBucket[] = []
  const firstBucket = Math.floor(Math.max(start, 0) / width)
  const lastBucket = Math.floor(Math.min(end, total - 1) / width)
  for (let index = firstBucket; index <= lastBucket; index++) {
    const first = Math.max(index * width, 0)
    const last = Math.min(index * width + width - 1, total - 1)
    const count = last - first + 1
    buckets.push({
      bucket: index,
      first_step: first,
      last_step: last,
      count,
      finite_count: count,
      min: 1,
      max: 1,
      sum: count,
    })
  }
  return buckets
}

interface Call {
  request: MetricBucketsRequest
  signal: AbortSignal | undefined
  release: () => void
}

/** A live source: `grow()` appends steps; a fetch answers with the data as of its start. */
class FakeSource implements MetricBucketSource {
  calls: Call[] = []
  catalogCalls: (MetricCatalogsRequest | undefined)[] = []
  manual = false
  failing = new Set<string>()
  catalogFailing = new Set<string>()
  /** Catalog fields to report instead, per `${modelId}/${key}`: a change a refresh must see. */
  catalogPatches = new Map<string, Partial<MetricCatalogEntry>>()
  /** While set, catalog reads wait for it; they read the data as of their start. */
  catalogGate: Promise<void> | null = null
  /** While set, catalog reads never answer and ignore their signal, as a stalled server. */
  catalogStalled = false
  catalogSignals: (AbortSignal | undefined)[] = []
  /** While set, bucket reads never answer and ignore their signal. */
  bucketsStalled = false
  statusRevision = 3
  /** Answer revision 2 catalogs, which have no count, min or max. */
  legacy = false
  metricKeys = KEYS
  private readonly lengths = new Map<string, number>()

  constructor(
    private readonly modelIds: string[],
    private readonly transport: ExperimentSnapshotStatus['transport'] = 'raw-range',
  ) {}

  length(modelId: string, key: string): number {
    return this.lengths.get(`${modelId}/${key}`) ?? STEPS
  }

  grow(modelId: string, key: string, steps: number): void {
    this.lengths.set(`${modelId}/${key}`, this.length(modelId, key) + steps)
  }

  async getExperimentStatuses(): Promise<ExperimentSnapshotStatus[]> {
    return this.modelIds.map((modelId) => ({
      modelId,
      revision: this.statusRevision,
      transport: this.transport,
      transportFallback: null,
      unknownNewerRevision: false,
      skippedMetricRows: 0,
      error: null,
    }))
  }

  async getMetricCatalogs(
    request?: MetricCatalogsRequest,
    signal?: AbortSignal,
  ): Promise<ExperimentResult<ExperimentMetricCatalog>[]> {
    this.catalogCalls.push(request)
    this.catalogSignals.push(signal)
    if (this.catalogStalled) return new Promise(() => {})
    const results = (request?.modelIds ?? this.modelIds).map(
      (modelId): ExperimentResult<ExperimentMetricCatalog> => {
        if (this.catalogFailing.has(modelId)) {
          return { modelId, ok: false, error: { code: 'needs-newer-reader', message: 'too new' } }
        }
        const catalog = catalogOf((key) => this.length(modelId, key), this.metricKeys)
        catalog.metrics = catalog.metrics.map((entry) => ({
          ...entry,
          ...(this.legacy ? { count: null, min: null, max: null } : {}),
          ...this.catalogPatches.get(`${modelId}/${entry.key}`),
        }))
        if (this.legacy) {
          Object.assign(catalog, { revision: 2, bucket_min_level: null, bucket_max_level: null })
        }
        return { modelId, ok: true, value: catalog }
      },
    )
    if (this.catalogGate) await this.catalogGate
    return results
  }

  getMetricBuckets(
    request: MetricBucketsRequest,
    signal?: AbortSignal,
  ): Promise<ExperimentResult<MetricBucketsResponse>[]> {
    const answers = (request.modelIds ?? []).map((modelId) => this.answer(modelId, request))
    if (this.bucketsStalled) {
      this.calls.push({ request, signal, release: () => {} })
      return new Promise(() => {})
    }
    return new Promise((resolve) => {
      const release = () => resolve(answers)
      this.calls.push({ request, signal, release })
      if (!this.manual) release()
    })
  }

  private answer(
    modelId: string,
    { keys, level, start_step, end_step }: MetricBucketsRequest,
  ): ExperimentResult<MetricBucketsResponse> {
    if (this.failing.has(modelId)) {
      return { modelId, ok: false, error: { code: 'read-failed', message: 'broken' } }
    }
    return {
      modelId,
      ok: true,
      value: {
        level,
        series: keys.map((key) => {
          const total = this.length(modelId, key)
          return {
            key,
            first_step: 0,
            last_step: total - 1,
            buckets: denseBuckets(level, start_step ?? 0, end_step ?? total - 1, total),
          }
        }),
      },
    }
  }
}

const REQUEST: BucketReadRequest = { modelIds: ['a'], keys: ['loss'], bucketBudget: 100 }

function summary(state: ChartState) {
  return {
    level: state.plan?.level ?? null,
    loading: state.loading,
    series: state.series.map((item) => [item.modelId, item.level, item.final, item.buckets.length]),
    errors: state.errors.map((item) => [item.modelId, item.error.code]),
  }
}

describe('MetricBucketStore', () => {
  beforeEach(() => vi.useFakeTimers())
  afterEach(() => vi.useRealTimers())

  function setup(
    modelIds = ['a'],
    cache = new BucketCache(),
    transport: ExperimentSnapshotStatus['transport'] = 'raw-range',
  ) {
    const source = new FakeSource(modelIds, transport)
    const store = new MetricBucketStore(source, { cache, debounceMs: DEBOUNCE })
    const states: ChartState[] = []
    const chart = store.subscribe((state) => states.push(state))
    return { source, store, states, chart, cache }
  }

  it('shows cached coarser data at once and replaces it with the planned level', async () => {
    const cache = new BucketCache()
    cache.write('a', 'loss', 6, 0, 24, denseBuckets(6, 0, STEPS - 1))
    const { source, states, chart } = setup(['a'], cache)

    chart.request(REQUEST)
    await vi.advanceTimersByTimeAsync(0)
    expect(states.map(summary)).toEqual([
      { level: null, loading: true, series: [], errors: [] },
      { level: 5, loading: true, series: [['a', 6, false, 25]], errors: [] },
    ])
    expect(source.calls).toHaveLength(0)

    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    expect(source.calls.map((call) => call.request)).toEqual([
      { modelIds: ['a'], keys: ['loss'], start_step: 0, end_step: 98 * 1024 - 1, level: 5 },
    ])
    expect(summary(chart.state)).toEqual({
      level: 5,
      loading: false,
      series: [['a', 5, true, 98]],
      errors: [],
    })
  })

  it('keeps a finer series on screen over coarser cached data until the planned level lands', async () => {
    const cache = new BucketCache()
    const { source, states, chart } = setup(['a'], cache)
    chart.request(REQUEST)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    expect(summary(chart.state).series).toEqual([['a', 5, true, 98]])

    cache.dropMetric('a', 'loss')
    cache.write('a', 'loss', 6, 0, 24, denseBuckets(6, 0, STEPS - 1))
    source.manual = true
    const before = states.length
    chart.request({ ...REQUEST, endStep: 90_000 })
    await vi.advanceTimersByTimeAsync(0)

    const shownLevels = states.slice(before).map((state) => state.series.map((item) => item.level))
    expect(shownLevels.length).toBeGreaterThan(0)
    for (const levels of shownLevels) expect(levels).toEqual([5])
  })

  it('serves a repeated request from the cache without fetching', async () => {
    const { source, chart } = setup()
    chart.request(REQUEST)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    chart.request({ ...REQUEST, startStep: 1000, endStep: 50_000, bucketBudget: 48 })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)

    expect(source.calls).toHaveLength(1)
    expect(summary(chart.state)).toEqual({
      level: 5,
      loading: false,
      series: [['a', 5, true, 49]],
      errors: [],
    })
  })

  it('debounces rapid requests into one fetch for the newest', async () => {
    const { source, chart } = setup()
    chart.request({ ...REQUEST, endStep: 10_000 })
    await vi.advanceTimersByTimeAsync(10)
    chart.request({ ...REQUEST, endStep: 30_000 })
    await vi.advanceTimersByTimeAsync(10)
    chart.request(REQUEST)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)

    expect(source.calls.map((call) => call.request.end_step)).toEqual([98 * 1024 - 1])
  })

  it('drops the late answer of a superseded request but keeps its buckets', async () => {
    const { source, states, chart, cache } = setup()
    source.manual = true
    chart.request({ ...REQUEST, endStep: 9999, bucketBudget: 1000 })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    chart.request(REQUEST)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    const [superseded, current] = source.calls

    expect(superseded?.signal?.aborted).toBe(true)
    expect(current?.signal?.aborted).toBe(false)
    const emitted = states.length
    superseded?.release()
    await vi.advanceTimersByTimeAsync(0)
    expect(states).toHaveLength(emitted)
    expect(cache.covers('a', 'loss', 2, 0, 624)).toBe(true)

    current?.release()
    await vi.advanceTimersByTimeAsync(0)
    expect(summary(chart.state)).toMatchObject({ level: 5, loading: false })
  })

  it('keeps a fetch in flight that the superseding request needs too', async () => {
    const { source, chart } = setup()
    source.manual = true
    chart.request(REQUEST)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    chart.request({ ...REQUEST })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)

    expect(source.calls).toHaveLength(1)
    expect(source.calls[0]?.signal?.aborted).toBe(false)
    source.calls[0]?.release()
    await vi.advanceTimersByTimeAsync(0)
    expect(summary(chart.state)).toMatchObject({ loading: false, series: [['a', 5, true, 98]] })
  })

  it('shares one fetch between charts that need the same buckets', async () => {
    const { source, store, chart } = setup()
    source.manual = true
    const other = store.subscribe(() => {})
    chart.request(REQUEST)
    other.request(REQUEST)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    expect(source.calls).toHaveLength(1)

    other.close()
    expect(source.calls[0]?.signal?.aborted).toBe(false)
    source.calls[0]?.release()
    await vi.advanceTimersByTimeAsync(0)
    expect(summary(chart.state).series).toEqual([['a', 5, true, 98]])
    expect(other.state.loading).toBe(true)
  })

  it('keeps errors per experiment and out of the cache', async () => {
    const { source, store, chart, cache } = setup(['a', 'b', 'c'])
    source.failing.add('b')
    source.catalogFailing.add('c')
    chart.request({ ...REQUEST, modelIds: ['a', 'b', 'c', 'gone'] })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)

    expect(summary(chart.state)).toEqual({
      level: 5,
      loading: false,
      series: [['a', 5, true, 98]],
      errors: [
        ['c', 'needs-newer-reader'],
        ['gone', 'read-failed'],
        ['b', 'read-failed'],
      ],
    })
    expect(cache.covers('b', 'loss', 5, 0, 97)).toBe(false)

    source.failing.clear()
    const retry = store.subscribe(() => {})
    retry.request({ ...REQUEST, modelIds: ['a', 'b'] })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    expect(source.calls.map((call) => call.request.modelIds)).toEqual([['a'], ['b'], ['b']])
    expect(summary(retry.state).series).toEqual([
      ['a', 5, true, 98],
      ['b', 5, true, 98],
    ])
  })

  it('never evicts the series of an open chart and fetches an evicted one again', async () => {
    const { source, store, chart } = setup(['a', 'b'], new BucketCache({ maxBuckets: 150 }))
    chart.request(REQUEST)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    const other = store.subscribe(() => {})
    other.request({ ...REQUEST, modelIds: ['b'] })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)

    expect(summary(chart.state).series).toEqual([['a', 5, true, 98]])
    expect(summary(other.state)).toMatchObject({ loading: false, series: [['b', 5, true, 98]] })
    expect(other.state.cacheOverflow).toBe(true)
    chart.close()
    // The same request again is served from the chart's own copy, not fetched again.
    other.request({ ...REQUEST, modelIds: ['b'] })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    expect(source.calls).toHaveLength(2)
    expect(summary(other.state)).toMatchObject({ loading: false, series: [['b', 5, true, 98]] })
    expect(other.state.cacheOverflow).toBe(true)

    // A changed request drops the copy; with 'a' unpinned the cache now holds 'b'.
    other.request({ ...REQUEST, modelIds: ['b'], bucketBudget: 99 })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    const reopened = store.subscribe(() => {})
    reopened.request(REQUEST)
    await vi.advanceTimersByTimeAsync(DEBOUNCE)

    expect(source.calls.map((call) => call.request.modelIds)).toEqual([['a'], ['b'], ['b'], ['a']])
    expect(other.state.cacheOverflow).toBe(false)
    expect(reopened.state.cacheOverflow).toBe(true)
  })

  it('fetches nothing again when a chart larger than the cache repeats its request', async () => {
    const { source, chart } = setup(['a'], new BucketCache({ maxBuckets: 150 }))
    chart.request({ ...REQUEST, keys: KEYS })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    for (let repeat = 0; repeat < 3; repeat++) {
      chart.request({ ...REQUEST, keys: KEYS })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
    }

    expect(source.calls).toHaveLength(1)
    expect(summary(chart.state)).toMatchObject({
      loading: false,
      series: [
        ['a', 5, true, 98],
        ['a', 5, true, 98],
      ],
    })
    expect(chart.state.cacheOverflow).toBe(true)
  })

  // Three series of 98 buckets cannot share a bound of 150: the chart still shows all three.
  it('serves a chart larger than the cache bound from its fetch answers', async () => {
    const { source, chart } = setup(['a'], new BucketCache({ maxBuckets: 150 }))
    source.manual = true
    chart.request({ ...REQUEST, keys: KEYS, endStep: 49_999 })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    source.calls[0]?.release()
    await vi.advanceTimersByTimeAsync(0)
    chart.request({ ...REQUEST, keys: KEYS })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    for (const call of source.calls.slice(1)) call.release()
    await vi.advanceTimersByTimeAsync(0)

    expect(source.calls.map((call) => [call.request.keys, call.request.start_step])).toEqual([
      [KEYS, 0],
      [KEYS, 49 * 1024],
    ])
    expect(summary(chart.state)).toEqual({
      level: 5,
      loading: false,
      series: [
        ['a', 5, true, 98],
        ['a', 5, true, 98],
      ],
      errors: [],
    })
    expect(chart.state.cacheOverflow).toBe(true)
    for (const series of chart.state.series) {
      expect(series.buckets.map((bucket) => bucket.bucket)).toEqual(
        Array.from({ length: 98 }, (_, index) => index),
      )
    }
  })

  it('stops emitting after close', async () => {
    const { states, chart } = setup()
    chart.request(REQUEST)
    chart.close()
    await vi.advanceTimersByTimeAsync(DEBOUNCE)

    expect(states).toHaveLength(1)
  })

  describe('live refresh', () => {
    const WIDTH = 1024
    // Steps 0..99_999 at level 5 are buckets 0..97; growing by 3000 steps makes the last
    // bucket 100, and bucket 97 (holding the old last step) was partial.
    const GROWN = 3000
    // A fixed visible range keeps the level at 5 while the run grows inside it.
    const LIVE: BucketReadRequest = {
      ...REQUEST,
      startStep: 0,
      endStep: 199_999,
      bucketBudget: 200,
    }

    async function shown(chart: ChartSubscription) {
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      return chart.state.series.map((item) => ({
        key: item.key,
        level: item.level,
        final: item.final,
        last: item.buckets.at(-1),
        total: item.buckets.reduce((sum, bucket) => sum + bucket.count, 0),
        unique: new Set(item.buckets.map((bucket) => bucket.bucket)).size === item.buckets.length,
      }))
    }

    it('drops only the tail of a grown metric and keeps unchanged metrics cached', async () => {
      const { source, store, chart, cache } = setup()
      chart.request({ ...REQUEST, keys: KEYS, startStep: 0, endStep: 99_999 })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(source.calls).toHaveLength(1)

      source.grow('a', 'loss', GROWN)
      await store.refreshCatalogs(['a'])

      expect(source.catalogCalls.at(-1)).toEqual({ modelIds: ['a'], refresh: true })
      expect(cache.missing('a', 'loss', 5, 0, 97)).toEqual([[97, 97]])
      expect(cache.covers('a', 'acc', 5, 0, 97)).toBe(true)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(source.calls.map((call) => call.request)).toEqual([
        expect.objectContaining({ keys: KEYS }),
        expect.objectContaining({ keys: ['loss'], start_step: 97 * WIDTH }),
      ])
    })

    it('re-plans an open chart, keeps showing its buckets and receives the new tail', async () => {
      const { source, store, states, chart } = setup()
      source.manual = true
      chart.request(LIVE)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      source.calls[0]?.release()
      await vi.advanceTimersByTimeAsync(0)

      source.grow('a', 'loss', GROWN)
      const emitted = states.length
      await store.refreshCatalogs(['a'])
      await vi.advanceTimersByTimeAsync(0)
      const during = states.slice(emitted)
      expect(during.length).toBeGreaterThan(0)
      for (const state of during) {
        expect(summary(state).series).toEqual([['a', 5, false, 98]])
      }

      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      source.calls.at(-1)?.release()
      expect(await shown(chart)).toEqual([
        {
          key: 'loss',
          level: 5,
          final: true,
          last: expect.objectContaining({ bucket: 100, last_step: STEPS + GROWN - 1 }),
          total: STEPS + GROWN,
          unique: true,
        },
      ])
    })

    it('neither loses nor duplicates data when a refresh lands during a fetch', async () => {
      const { source, store, chart, cache } = setup()
      source.manual = true
      chart.request(LIVE)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      const stale = source.calls[0]

      source.grow('a', 'loss', GROWN)
      await store.refreshCatalogs(['a'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      const fresh = source.calls.at(-1)
      expect(fresh).not.toBe(stale)
      fresh?.release()
      await vi.advanceTimersByTimeAsync(0)
      stale?.release()
      await vi.advanceTimersByTimeAsync(0)

      expect(await shown(chart)).toEqual([
        expect.objectContaining({ final: true, total: STEPS + GROWN, unique: true }),
      ])
      // The stale answer still held bucket 97 as it was before the run grew.
      expect(cache.read('a', 'loss', 5, 97, 97)).toEqual([
        expect.objectContaining({ count: WIDTH, last_step: 98 * WIDTH - 1 }),
      ])
      expect(cache.covers('a', 'loss', 5, 0, 100)).toBe(true)
    })

    it('fetches nothing for experiments whose metrics did not change', async () => {
      const { source, store, chart } = setup(['a', 'b'])
      chart.request({ ...REQUEST, modelIds: ['a', 'b'] })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      const before = source.calls.length

      source.grow('a', 'acc', GROWN)
      await store.refreshCatalogs(['a', 'b'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)

      expect(source.calls).toHaveLength(before)
      expect(summary(chart.state).series).toEqual([
        ['a', 5, true, 98],
        ['b', 5, true, 98],
      ])
    })
  })

  describe('refresh semantics', () => {
    async function shownChart(modelIds = ['a']) {
      const context = setup(modelIds)
      context.chart.request({ ...REQUEST, modelIds, keys: KEYS, startStep: 0, endStep: 99_999 })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(context.source.calls).toHaveLength(modelIds.length)
      return context
    }

    it.each([
      { change: 'count', patch: { count: STEPS - 1 } },
      { change: 'first_step', patch: { first_step: -5 } },
      { change: 'min', patch: { min: -1 } },
      { change: 'max', patch: { max: 2 } },
    ])('drops the whole metric when its $change changed without growing', async ({ patch }) => {
      const { source, store, cache, chart } = await shownChart()
      source.catalogPatches.set('a/loss', patch)
      await store.refreshCatalogs(['a'])

      expect(cache.missing('a', 'loss', 5, 0, 97)).toEqual([[0, 97]])
      expect(cache.covers('a', 'acc', 5, 0, 97)).toBe(true)
      expect(summary(chart.state).series).toEqual([
        ['a', 5, false, 98],
        ['a', 5, true, 98],
      ])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(source.calls.at(-1)?.request).toMatchObject({ keys: ['loss'], start_step: 0 })
      expect(summary(chart.state).series).toEqual([
        ['a', 5, true, 98],
        ['a', 5, true, 98],
      ])
    })

    it('returns per-experiment failures and marks kept data not final until it lands', async () => {
      const { source, store, chart } = await shownChart(['a', 'b'])
      source.catalogFailing.add('b')
      source.grow('a', 'loss', 3000)
      source.failing.add('a')

      const failures = await store.refreshCatalogs(['a', 'b'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)

      expect([...failures]).toEqual([['b', { code: 'needs-newer-reader', message: 'too new' }]])
      expect(summary(chart.state)).toEqual({
        level: 5,
        loading: false,
        series: [
          ['a', 5, false, 98],
          ['a', 5, true, 98],
          ['b', 5, true, 98],
          ['b', 5, true, 98],
        ],
        errors: [['a', 'read-failed']],
      })
    })

    it('keeps the refresh queue going after a refresh rejects', async () => {
      const { source, store } = setup()
      vi.spyOn(source, 'getMetricCatalogs').mockRejectedValueOnce(new Error('down'))

      await expect(store.refreshCatalogs(['a'])).rejects.toThrow('down')
      source.grow('a', 'loss', 10)
      await expect(store.refreshCatalogs(['a'])).resolves.toEqual(new Map())
      const loss = (await store.loadCatalogs()).catalogs.get('a')?.metrics[0]
      expect(loss?.last_step).toBe(STEPS + 9)
    })

    it('runs refreshes in call order, so a slow earlier one never wins', async () => {
      const { source, store } = await shownChart()
      let release = () => {}
      source.catalogGate = new Promise<void>((resolve) => (release = resolve))
      source.grow('a', 'loss', 1000)
      const slow = store.refreshCatalogs(['a'])
      await vi.advanceTimersByTimeAsync(0)
      source.catalogGate = null
      source.grow('a', 'loss', 1000)
      const fast = store.refreshCatalogs(['a'])
      await vi.advanceTimersByTimeAsync(0)
      release()
      await Promise.all([slow, fast])

      const catalogs = await store.loadCatalogs()
      const loss = catalogs.catalogs.get('a')?.metrics.find((entry) => entry.key === 'loss')
      expect(loss?.last_step).toBe(STEPS + 2000 - 1)
    })

    it('reloads an experiment completely on request', async () => {
      const { source, store, cache, chart } = await shownChart(['a', 'b'])
      await store.reload(['a'])

      expect(cache.missing('a', 'loss', 5, 0, 97)).toEqual([[0, 97]])
      expect(cache.missing('a', 'acc', 5, 0, 97)).toEqual([[0, 97]])
      expect(cache.covers('b', 'loss', 5, 0, 97)).toBe(true)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(source.calls.at(-1)?.request).toMatchObject({ modelIds: ['a'], keys: KEYS })
      expect(summary(chart.state).series.every((series) => series[2] === true)).toBe(true)
    })
  })

  describe('refresh of a legacy catalog without count, min and max', () => {
    async function shownLegacyChart() {
      const context = setup(['a'], new BucketCache(), 'zip-full')
      context.source.legacy = true
      context.source.statusRevision = 2
      context.chart.request({ ...REQUEST, keys: KEYS, startStep: 0, endStep: 99_999 })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(context.source.calls).toHaveLength(1)
      expect(summary(context.chart.state).series).toEqual([
        ['a', 5, true, 98],
        ['a', 5, true, 98],
      ])
      return context
    }

    it('drops only the tail when the last step grew', async () => {
      const { source, store, cache } = await shownLegacyChart()
      source.grow('a', 'loss', 3000)
      await store.refreshCatalogs(['a'])

      expect(cache.missing('a', 'loss', 5, 0, 97)).toEqual([[97, 97]])
      expect(cache.covers('a', 'acc', 5, 0, 97)).toBe(true)
    })

    it('drops the whole metric when the first step changed', async () => {
      const { source, store, cache } = await shownLegacyChart()
      source.catalogPatches.set('a/loss', { first_step: -5 })
      await store.refreshCatalogs(['a'])

      expect(cache.missing('a', 'loss', 5, 0, 97)).toEqual([[0, 97]])
      expect(cache.covers('a', 'acc', 5, 0, 97)).toBe(true)
    })

    it('drops and fetches nothing when the steps did not change', async () => {
      const { source, store, cache } = await shownLegacyChart()
      await store.refreshCatalogs(['a'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)

      expect(cache.covers('a', 'loss', 5, 0, 97)).toBe(true)
      expect(cache.covers('a', 'acc', 5, 0, 97)).toBe(true)
      expect(source.calls).toHaveLength(1)
    })
  })

  describe('listener re-entrancy and failures', () => {
    it('runs only the newer request when the listener requests during an emission', async () => {
      const source = new FakeSource(['a'])
      const store = new MetricBucketStore(source, { debounceMs: DEBOUNCE })
      const narrow = { ...REQUEST, startStep: 0, endStep: 4999 }
      let emissions = 0
      const chart = store.subscribe((state) => {
        emissions++
        if (emissions === 2 && state.plan) chart.request(narrow)
      })
      chart.request(REQUEST)
      await vi.advanceTimersByTimeAsync(DEBOUNCE * 2)

      expect(source.calls.map((call) => call.request.end_step)).toEqual([79 * 64 - 1])
      expect(chart.state).toMatchObject({ request: narrow, loading: false })
    })

    it('starts no fetch when the listener closes the chart during an emission', async () => {
      for (const closeAt of [1, 2]) {
        const source = new FakeSource(['a'])
        const store = new MetricBucketStore(source, { debounceMs: DEBOUNCE })
        let emissions = 0
        const chart = store.subscribe(() => {
          if (++emissions === closeAt) chart.close()
        })
        chart.request(REQUEST)
        await vi.advanceTimersByTimeAsync(DEBOUNCE * 2)

        expect(source.calls, `close at emission ${closeAt}`).toHaveLength(0)
        expect(emissions).toBe(closeAt)
      }
    })

    it('normalises float ranges and widths from a chart instead of failing', async () => {
      const { source, chart } = setup()
      chart.request({ ...REQUEST, startStep: 10.5, endStep: 900.25, bucketBudget: 812.5 })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)

      expect(source.calls.map((call) => [call.request.start_step, call.request.end_step])).toEqual([
        [8, 903],
      ])
      expect(chart.state).toMatchObject({ loading: false, errors: [] })
    })

    it('emits an error and releases superseded fetches when planning fails', async () => {
      const { source, store, chart } = setup()
      source.manual = true
      chart.request(REQUEST)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      const superseded = source.calls[0]
      // A catalog the planner rejects: steps must be integers.
      source.catalogPatches.set('a/loss', { first_step: 0.5 })
      await store.refreshCatalogs(['a'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)

      expect(superseded?.signal?.aborted).toBe(true)
      expect(chart.state).toMatchObject({
        loading: false,
        plan: null,
        errors: [{ modelId: 'a', error: { code: 'read-failed' } }],
      })
    })
  })

  it('does not degrade the plan of a local experiment for its row cost', async () => {
    const source = new FakeSource(['a'], 'zip-full')
    const store = new MetricBucketStore(source, {
      debounceMs: DEBOUNCE,
      planner: { maxCostRows: 10 },
    })
    const chart = store.subscribe(() => {})
    chart.request({ ...REQUEST, endStep: 999, bucketBudget: 1000 })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)

    expect(chart.state.plan).toMatchObject({ level: 0, degraded: false, overBudget: false })
  })

  it('drops the whole metric when it grew and its first step changed too', async () => {
    const { source, store, cache, chart } = setup()
    chart.request({ ...REQUEST, keys: KEYS, startStep: 0, endStep: 99_999 })
    await vi.advanceTimersByTimeAsync(DEBOUNCE)
    source.grow('a', 'loss', 3000)
    // An early step was written as well: bucket 0, far from the tail, is stale.
    source.catalogPatches.set('a/loss', { first_step: -5 })
    await store.refreshCatalogs(['a'])

    expect(cache.missing('a', 'loss', 5, 0, 97)).toEqual([[0, 97]])
    expect(cache.covers('a', 'acc', 5, 0, 97)).toBe(true)
  })

  describe('timeouts and dispose', () => {
    const TIMEOUT = 1000

    function timedSetup() {
      const source = new FakeSource(['a'])
      const store = new MetricBucketStore(source, {
        debounceMs: DEBOUNCE,
        requestTimeoutMs: TIMEOUT,
      })
      const chart = store.subscribe(() => {})
      return { source, store, chart }
    }

    it('ends a stalled first catalog load in an error state and retries it later', async () => {
      const { source, store, chart } = timedSetup()
      source.catalogStalled = true
      chart.request(REQUEST)
      await vi.advanceTimersByTimeAsync(TIMEOUT)

      expect(chart.state).toMatchObject({
        loading: false,
        errors: [{ modelId: 'a', error: { code: 'timed-out' } }],
      })
      expect(source.catalogSignals[0]?.aborted).toBe(true)
      source.catalogStalled = false
      chart.request(REQUEST)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(summary(chart.state)).toMatchObject({ loading: false, series: [['a', 5, true, 98]] })
      expect(await store.loadCatalogs()).toMatchObject({ statuses: [{ modelId: 'a' }] })
    })

    it('lets the refresh queue advance past a stalled refresh', async () => {
      const { source, store } = timedSetup()
      await store.loadCatalogs()
      source.catalogStalled = true
      const stalled = store.refreshCatalogs(['a'])
      const reload = store.reload(['a'])
      await vi.advanceTimersByTimeAsync(TIMEOUT)
      source.catalogStalled = false
      await vi.advanceTimersByTimeAsync(TIMEOUT)

      expect([...(await stalled)]).toEqual([['a', expect.objectContaining({ code: 'timed-out' })]])
      expect([...(await reload)]).toEqual([['a', expect.objectContaining({ code: 'timed-out' })]])
      source.grow('a', 'loss', 10)
      await store.refreshCatalogs(['a'])
      const loss = (await store.loadCatalogs()).catalogs.get('a')?.metrics[0]
      expect(loss?.last_step).toBe(STEPS + 9)
    })

    it('fails a stalled bucket fetch with a timeout and keeps what the chart shows', async () => {
      const { source, store, chart } = timedSetup()
      chart.request({ ...REQUEST, startStep: 0, endStep: 199_999, bucketBudget: 200 })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      source.grow('a', 'loss', 3000)
      source.bucketsStalled = true
      await store.refreshCatalogs(['a'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE + TIMEOUT)

      expect(source.calls.at(-1)?.signal?.aborted).toBe(true)
      expect(summary(chart.state)).toEqual({
        level: 5,
        loading: false,
        series: [['a', 5, false, 98]],
        errors: [['a', 'timed-out']],
      })
    })

    it('dispose closes every chart, aborts what is in flight and empties its cache', async () => {
      const { source, store, chart } = timedSetup()
      const states: ChartState[] = []
      const other = store.subscribe((state) => states.push(state))
      source.manual = true
      chart.request(REQUEST)
      other.request({ ...REQUEST, keys: ['acc'] })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      const emitted = states.length

      store.dispose()
      source.calls[0]?.release()
      await vi.advanceTimersByTimeAsync(TIMEOUT)

      expect(source.calls[0]?.signal?.aborted).toBe(true)
      expect(states).toHaveLength(emitted)
      expect(store.cache.bucketCount).toBe(0)
      await expect(store.loadCatalogs()).rejects.toMatchObject({ name: 'AbortError' })
      await expect(store.refreshCatalogs(['a'])).rejects.toMatchObject({ name: 'AbortError' })
      const late = store.subscribe(() => {})
      late.request(REQUEST)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(late.state.request).toBeNull()
      expect(source.calls).toHaveLength(1)
    })

    it('aborts a stalled first catalog load on dispose', async () => {
      const { source, store } = timedSetup()
      source.catalogStalled = true
      const loading = store.loadCatalogs()
      store.dispose()

      await expect(loading).rejects.toMatchObject({ name: 'AbortError' })
      expect(source.catalogSignals[0]?.aborted).toBe(true)
    })
  })

  describe('statuses', () => {
    it('loads the statuses after the catalogs and refreshes them with the catalogs', async () => {
      const { source, store } = setup()
      expect((await store.loadCatalogs()).statuses).toEqual([
        expect.objectContaining({ modelId: 'a', revision: 3 }),
      ])
      source.statusRevision = 4
      await store.refreshCatalogs(['a'])
      expect((await store.loadCatalogs()).statuses).toEqual([
        expect.objectContaining({ modelId: 'a', revision: 4 }),
      ])
    })
  })

  describe('keeping what a chart shows', () => {
    it('emits the shown series, not an empty state, when the request changes', async () => {
      const { states, chart } = setup()
      chart.request(REQUEST)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      const emitted = states.length

      chart.request({ ...REQUEST, startStep: 0, endStep: 9999, bucketBudget: 1000 })
      const [first] = states.slice(emitted)
      expect(first && summary(first)).toEqual({
        level: null,
        loading: true,
        series: [['a', 5, false, 98]],
        errors: [],
      })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      expect(summary(chart.state)).toMatchObject({ loading: false, series: [['a', 2, true, 625]] })
    })

    it('starts a new subscription with the series it is given until better data arrives', async () => {
      const { source, store } = setup()
      const shown = { modelId: 'a', key: 'loss', level: 5, final: true, buckets: [] }
      source.manual = true
      const states: ChartState[] = []
      const chart = store.subscribe((state) => states.push(state), { series: [shown] })
      chart.request(REQUEST)
      await vi.advanceTimersByTimeAsync(DEBOUNCE)

      expect(states.map(summary).every((state) => state.series.length === 1)).toBe(true)
      expect(chart.state.series[0]).toMatchObject({ final: false, level: 5 })
      source.calls[0]?.release()
      await vi.advanceTimersByTimeAsync(0)
      expect(summary(chart.state).series).toEqual([['a', 5, true, 98]])
    })
  })

  describe('batching across charts', () => {
    const PAGE = 12

    function page(modelIds = ['a', 'b']) {
      const source = new FakeSource(modelIds)
      source.manual = true
      const store = new MetricBucketStore(source, { debounceMs: DEBOUNCE })
      const keys = Array.from({ length: PAGE }, (_, index) => `m${index}`)
      source.metricKeys = keys
      const charts = keys.map((key) => {
        const chart = store.subscribe(() => {})
        chart.request({ ...REQUEST, modelIds, keys: [key], startStep: 0, endStep: STEPS - 1 })
        return chart
      })
      return { source, store, charts, keys }
    }

    it('merges the fetches of a page of charts into one query per experiment', async () => {
      const { source, charts, keys } = page()
      await vi.advanceTimersByTimeAsync(DEBOUNCE)

      expect(source.calls.map((call) => [call.request.modelIds, call.request.keys])).toEqual([
        [['a'], keys],
        [['b'], keys],
      ])
      for (const call of source.calls) call.release()
      await vi.advanceTimersByTimeAsync(0)
      for (const [index, chart] of charts.entries()) {
        expect(chart.state.series.map((series) => [series.modelId, series.key])).toEqual([
          ['a', keys[index]],
          ['b', keys[index]],
        ])
        expect(chart.state.loading).toBe(false)
      }
    })

    it('aborts a merged fetch only when every chart in it has gone', async () => {
      const { source, charts } = page(['a'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      const [merged] = source.calls

      for (const chart of charts.slice(1)) chart.close()
      expect(merged?.signal?.aborted).toBe(false)
      merged?.release()
      await vi.advanceTimersByTimeAsync(0)
      expect(summary(charts[0]!.state)).toMatchObject({ loading: false })
      expect(charts[0]?.state.series).toHaveLength(1)

      const again = page(['a'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      for (const chart of again.charts) chart.close()
      expect(again.source.calls[0]?.signal?.aborted).toBe(true)
    })

    it('keeps one chart superseding its request from affecting the merged fetch', async () => {
      const { source, charts } = page(['a'])
      await vi.advanceTimersByTimeAsync(DEBOUNCE)
      charts[0]?.request({ ...REQUEST, keys: ['m0'], startStep: 0, endStep: 999 })
      await vi.advanceTimersByTimeAsync(DEBOUNCE)

      expect(source.calls[0]?.signal?.aborted).toBe(false)
      for (const call of source.calls) call.release()
      await vi.advanceTimersByTimeAsync(0)
      expect(charts.every((chart) => !chart.state.loading)).toBe(true)
    })

    it('still flushes a window that keeps being extended', async () => {
      const source = new FakeSource(['a'])
      const store = new MetricBucketStore(source, { debounceMs: DEBOUNCE })
      const busy = store.subscribe(() => {})
      const quiet = store.subscribe(() => {})
      quiet.request(REQUEST)
      for (let tick = 0; tick < 10; tick++) {
        busy.request({ ...REQUEST, keys: ['acc'], endStep: 1000 + tick })
        await vi.advanceTimersByTimeAsync(DEBOUNCE / 2)
      }

      expect(source.calls.length).toBeGreaterThan(0)
      expect(quiet.state.loading).toBe(false)
    })
  })

  it('gives the union step range of a metric over the experiments', async () => {
    const { source, store } = setup(['a', 'b'])
    source.grow('b', 'loss', 50)
    const catalogs = await store.loadCatalogs()

    expect(metricStepRange(catalogs, 'loss')).toEqual({ first: 0, last: STEPS + 49 })
    expect(metricStepRange(catalogs, 'loss', ['a'])).toEqual({ first: 0, last: STEPS - 1 })
    expect(metricStepRange(catalogs, 'missing')).toBeNull()
    expect(metricStepRanges(catalogs).get('acc')).toEqual({ first: 0, last: STEPS - 1 })
  })
})
