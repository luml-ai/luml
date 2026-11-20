import { describe, expect, it } from 'vitest'
import { BucketCache } from '../BucketCache'
import { planBucketRead, type BucketReadPlan, type BucketReadRequest } from '../planner'
import type { ExperimentMetricCatalog, MetricCatalogEntry } from '../types'

const MILLION = 1_000_000

function entry(key: string, first: number, last: number, count = last - first + 1) {
  return { key, first_step: first, last_step: last, count, min: 0, max: 1 } as MetricCatalogEntry
}

const rev3: ExperimentMetricCatalog = {
  revision: 3,
  bucket_min_level: 3,
  bucket_max_level: 12,
  skipped_rows: 0,
  metrics: [entry('loss', 0, MILLION - 1), entry('acc', 0, MILLION - 1)],
}
const rev2: ExperimentMetricCatalog = {
  revision: 2,
  bucket_min_level: null,
  bucket_max_level: null,
  skipped_rows: 0,
  metrics: [entry('loss', 0, MILLION - 1)],
}
const smallRev2: ExperimentMetricCatalog = { ...rev2, metrics: [entry('loss', -500, 499)] }

function cacheWith(...ranges: [string, number, number, number][]): BucketCache {
  const cache = new BucketCache()
  for (const [key, level, first, last] of ranges) cache.write('new', key, level, first, last, [])
  return cache
}

interface PlannerCase {
  name: string
  catalogs: Record<string, ExperimentMetricCatalog>
  request: BucketReadRequest
  cache?: BucketCache
  maxCostRows?: number
  local?: string[]
  plan: BucketReadPlan | null
}

const whole = { modelIds: ['new'], keys: ['loss'], bucketBudget: 1000 }

const CASES: PlannerCase[] = [
  {
    name: 'a stored level for the union range of a revision 3 experiment',
    catalogs: { new: rev3 },
    request: whole,
    plan: {
      level: 5,
      requestedLevel: 5,
      degraded: false,
      overBudget: false,
      startStep: 0,
      endStep: 999_999,
      firstBucket: 0,
      lastBucket: 976,
      experiments: [
        {
          modelId: 'new',
          source: 'bucket-table',
          series: [{ key: 'loss', firstBucket: 0, lastBucket: 976 }],
          fetches: [
            { keys: ['loss'], firstBucket: 0, lastBucket: 976, startStep: 0, endStep: 1_000_447 },
          ],
          cost: { rows: 977, bytes: 977 * 64 },
        },
      ],
      cost: { rows: 977, bytes: 977 * 64 },
    },
  },
  {
    name: 'only the buckets the cache misses',
    catalogs: { new: rev3 },
    request: whole,
    cache: cacheWith(['loss', 5, 0, 499], ['loss', 5, 600, 700]),
    plan: {
      level: 5,
      requestedLevel: 5,
      degraded: false,
      overBudget: false,
      startStep: 0,
      endStep: 999_999,
      firstBucket: 0,
      lastBucket: 976,
      experiments: [
        {
          modelId: 'new',
          source: 'bucket-table',
          series: [{ key: 'loss', firstBucket: 0, lastBucket: 976 }],
          fetches: [
            {
              keys: ['loss'],
              firstBucket: 500,
              lastBucket: 599,
              startStep: 512_000,
              endStep: 614_399,
            },
            {
              keys: ['loss'],
              firstBucket: 701,
              lastBucket: 976,
              startStep: 717_824,
              endStep: 1_000_447,
            },
          ],
          cost: { rows: 376, bytes: 376 * 64 },
        },
      ],
      cost: { rows: 376, bytes: 376 * 64 },
    },
  },
  {
    name: 'nothing when the cache holds the planned level',
    catalogs: { new: rev3 },
    request: whole,
    cache: cacheWith(['loss', 5, -10, 2000]),
    plan: {
      level: 5,
      requestedLevel: 5,
      degraded: false,
      overBudget: false,
      startStep: 0,
      endStep: 999_999,
      firstBucket: 0,
      lastBucket: 976,
      experiments: [
        {
          modelId: 'new',
          source: 'bucket-table',
          series: [{ key: 'loss', firstBucket: 0, lastBucket: 976 }],
          fetches: [],
          cost: { rows: 0, bytes: 0 },
        },
      ],
      cost: { rows: 0, bytes: 0 },
    },
  },
  {
    name: 'a raw group-by below the stored levels while it is within budget',
    catalogs: { new: rev3 },
    request: { ...whole, startStep: 0, endStep: 99_999, bucketBudget: 50_000 },
    plan: {
      level: 2,
      requestedLevel: 2,
      degraded: false,
      overBudget: false,
      startStep: 0,
      endStep: 99_999,
      firstBucket: 0,
      lastBucket: 6249,
      experiments: [
        {
          modelId: 'new',
          source: 'raw-group-by',
          series: [{ key: 'loss', firstBucket: 0, lastBucket: 6249 }],
          fetches: [
            { keys: ['loss'], firstBucket: 0, lastBucket: 6249, startStep: 0, endStep: 99_999 },
          ],
          cost: { rows: 100_000, bytes: 100_000 * 32 },
        },
      ],
      cost: { rows: 100_000, bytes: 100_000 * 32 },
    },
  },
  {
    name: 'a coarser stored level when the raw read exceeds the budget',
    catalogs: { new: rev3 },
    request: { ...whole, startStep: 0, endStep: 99_999, bucketBudget: 50_000 },
    maxCostRows: 50_000,
    plan: {
      level: 3,
      requestedLevel: 2,
      degraded: true,
      overBudget: false,
      startStep: 0,
      endStep: 99_999,
      firstBucket: 0,
      lastBucket: 1562,
      experiments: [
        {
          modelId: 'new',
          source: 'bucket-table',
          series: [{ key: 'loss', firstBucket: 0, lastBucket: 1562 }],
          fetches: [
            { keys: ['loss'], firstBucket: 0, lastBucket: 1562, startStep: 0, endStep: 100_031 },
          ],
          cost: { rows: 1563, bytes: 1563 * 64 },
        },
      ],
      cost: { rows: 1563, bytes: 1563 * 64 },
    },
  },
  {
    name: 'the cheapest level, flagged, when no level of an old revision fits the budget',
    catalogs: { old: rev2 },
    request: { ...whole, modelIds: ['old'] },
    plan: {
      level: 5,
      requestedLevel: 5,
      degraded: false,
      overBudget: true,
      startStep: 0,
      endStep: 999_999,
      firstBucket: 0,
      lastBucket: 976,
      experiments: [
        {
          modelId: 'old',
          source: 'raw-group-by',
          series: [{ key: 'loss', firstBucket: 0, lastBucket: 976 }],
          fetches: [
            { keys: ['loss'], firstBucket: 0, lastBucket: 976, startStep: 0, endStep: 1_000_447 },
          ],
          cost: { rows: MILLION, bytes: MILLION * 32 },
        },
      ],
      cost: { rows: MILLION, bytes: MILLION * 32 },
    },
  },
  {
    name: 'the requested level for a local experiment however many rows it reads',
    catalogs: { old: rev2 },
    request: { ...whole, modelIds: ['old'] },
    local: ['old'],
    plan: {
      level: 5,
      requestedLevel: 5,
      degraded: false,
      overBudget: false,
      startStep: 0,
      endStep: 999_999,
      firstBucket: 0,
      lastBucket: 976,
      experiments: [
        {
          modelId: 'old',
          source: 'raw-group-by',
          series: [{ key: 'loss', firstBucket: 0, lastBucket: 976 }],
          fetches: [
            { keys: ['loss'], firstBucket: 0, lastBucket: 976, startStep: 0, endStep: 1_000_447 },
          ],
          cost: { rows: MILLION, bytes: MILLION * 32 },
        },
      ],
      cost: { rows: MILLION, bytes: MILLION * 32 },
    },
  },
  {
    name: 'a coarse aggregate above the stored levels',
    catalogs: { new: rev3 },
    request: { ...whole, startStep: 0, endStep: 4 ** 14 - 1, bucketBudget: 1 },
    plan: {
      level: 14,
      requestedLevel: 14,
      degraded: false,
      overBudget: false,
      startStep: 0,
      endStep: 4 ** 14 - 1,
      firstBucket: 0,
      lastBucket: 0,
      experiments: [
        {
          modelId: 'new',
          source: 'coarse-aggregate',
          series: [{ key: 'loss', firstBucket: 0, lastBucket: 0 }],
          fetches: [
            { keys: ['loss'], firstBucket: 0, lastBucket: 0, startStep: 0, endStep: 4 ** 14 - 1 },
          ],
          cost: { rows: 1, bytes: 64 },
        },
      ],
      cost: { rows: 1, bytes: 64 },
    },
  },
  {
    name: 'one level for a mixed comparison, keys grouped by what they miss',
    catalogs: { new: rev3, small: smallRev2 },
    request: {
      modelIds: ['small', 'new', 'unloaded'],
      keys: ['loss', 'acc', 'gone'],
      startStep: -1000,
      endStep: 2999,
      bucketBudget: 100,
    },
    cache: cacheWith(['acc', 3, 0, 10]),
    plan: {
      level: 3,
      requestedLevel: 3,
      degraded: false,
      overBudget: false,
      startStep: -1000,
      endStep: 2999,
      firstBucket: -16,
      lastBucket: 46,
      experiments: [
        {
          modelId: 'small',
          source: 'raw-group-by',
          series: [{ key: 'loss', firstBucket: -8, lastBucket: 7 }],
          fetches: [
            { keys: ['loss'], firstBucket: -16, lastBucket: 46, startStep: -1024, endStep: 3007 },
          ],
          cost: { rows: 1000, bytes: 1000 * 32 },
        },
        {
          modelId: 'new',
          source: 'bucket-table',
          series: [
            { key: 'loss', firstBucket: 0, lastBucket: 46 },
            { key: 'acc', firstBucket: 0, lastBucket: 46 },
          ],
          fetches: [
            { keys: ['loss'], firstBucket: -16, lastBucket: 46, startStep: -1024, endStep: 3007 },
            { keys: ['acc'], firstBucket: 11, lastBucket: 46, startStep: 704, endStep: 3007 },
          ],
          cost: { rows: 47 + 36, bytes: (47 + 36) * 64 },
        },
      ],
      cost: { rows: 1083, bytes: 1000 * 32 + 83 * 64 },
    },
  },
  {
    name: 'empty series and no fetches for a range outside the data',
    catalogs: { new: rev3 },
    request: { ...whole, startStep: 2 * MILLION, endStep: 3 * MILLION },
    plan: {
      level: 5,
      requestedLevel: 5,
      degraded: false,
      overBudget: false,
      startStep: 2 * MILLION,
      endStep: 3 * MILLION,
      firstBucket: 1953,
      lastBucket: 2929,
      experiments: [
        {
          modelId: 'new',
          source: 'bucket-table',
          series: [{ key: 'loss', firstBucket: 1953, lastBucket: 976 }],
          fetches: [],
          cost: { rows: 0, bytes: 0 },
        },
      ],
      cost: { rows: 0, bytes: 0 },
    },
  },
  {
    name: 'no plan when no range is given and no series has points',
    catalogs: { new: rev3 },
    request: { ...whole, keys: ['gone'] },
    plan: null,
  },
]

describe('planBucketRead', () => {
  it.each(CASES)('plans $name', ({ catalogs, request, cache, maxCostRows, local, plan }) => {
    const options = {
      ...(maxCostRows === undefined ? {} : { maxCostRows }),
      localModelIds: new Set(local ?? []),
    }
    const view = cache ?? new BucketCache()
    const first = planBucketRead(new Map(Object.entries(catalogs)), request, view, options)

    expect(first).toEqual(plan)
    expect(planBucketRead(new Map(Object.entries(catalogs)), request, view, options)).toEqual(first)
  })

  it('assumes a dense metric when a legacy catalog has no count', () => {
    const legacy: ExperimentMetricCatalog = {
      ...rev2,
      metrics: rev2.metrics.map((item) => ({ ...item, count: null, min: null, max: null })),
    }
    const sparse: ExperimentMetricCatalog = {
      ...rev2,
      metrics: [entry('loss', 0, MILLION - 1, 1000)],
    }
    const request = { ...whole, modelIds: ['old'], startStep: 0, endStep: 99_999 }
    const options = { localModelIds: new Set<string>() }
    const plan = (catalog: ExperimentMetricCatalog) =>
      planBucketRead(new Map([['old', catalog]]), request, new BucketCache(), options)

    expect(plan(legacy)).toEqual(plan(rev2))
    expect(plan(legacy)!.cost.rows).toBeGreaterThanOrEqual(100_000)
    expect(plan(sparse)!.cost.rows).toBeLessThan(1000)
  })

  it('keeps the bucket count of an unaligned range under the server cap', () => {
    const plan = planBucketRead(
      new Map([['new', rev3]]),
      { ...whole, startStep: 1, endStep: 20_000, bucketBudget: 100_000 },
      new BucketCache(),
    )

    expect(plan?.level).toBe(1)
    expect((plan?.lastBucket ?? 0) - (plan?.firstBucket ?? 0) + 1).toBeLessThanOrEqual(20_000)
  })

  // Chart axes and pixel widths are floats; none of these may throw.
  it.each([
    { bucketBudget: 812.5, steps: [0, 999_999], level: 6 },
    { bucketBudget: 0, steps: [0, 999_999], level: 10 },
    { bucketBudget: -3, steps: [0, 999_999], level: 10 },
    { bucketBudget: NaN, steps: [0, 999_999], level: 10 },
    { bucketBudget: Infinity, steps: [0, 999_999], level: 3 },
    { startStep: 10.5, endStep: 900.25, steps: [11, 900], level: 0 },
    { startStep: NaN, endStep: 500, steps: [0, 500], level: 0 },
    { startStep: -Infinity, endStep: 1e300, steps: [-9007199254740991, 9007199254740991] },
    { startStep: -1e300, endStep: -1e299, steps: [-9007199254740991, -9007199254740991] },
  ])('normalises budget $bucketBudget and steps $startStep..$endStep', (input) => {
    const { steps, level, ...request } = input
    const plan = planBucketRead(
      new Map([['new', rev3]]),
      { ...whole, ...request, bucketBudget: request.bucketBudget ?? 1000 },
      new BucketCache(),
    )

    expect([plan?.startStep, plan?.endStep]).toEqual(steps)
    if (level !== undefined) expect(plan?.requestedLevel).toBe(level)
  })

  it('plans the part of a metric inside +-(2^53 - 1) and leaves out one wholly beyond', () => {
    const unsafe: ExperimentMetricCatalog = {
      ...rev3,
      metrics: [entry('loss', -(2 ** 60), 2 ** 60), entry('time_ns', 1.7e18, 1.8e18)],
    }
    const request = { modelIds: ['new'], keys: ['loss', 'time_ns'], bucketBudget: 1000 }
    const plan = (overrides: Partial<BucketReadRequest> = {}) =>
      planBucketRead(new Map([['new', unsafe]]), { ...request, ...overrides }, new BucketCache())

    for (const planned of [plan(), plan({ startStep: 1.7e18, endStep: 1.8e18 })]) {
      expect(planned?.experiments[0]?.series.map((series) => series.key)).toEqual(['loss'])
    }
    expect([plan()?.startStep, plan()?.endStep]).toEqual([
      -Number.MAX_SAFE_INTEGER,
      Number.MAX_SAFE_INTEGER,
    ])
    expect(plan({ keys: ['time_ns'] })).toBeNull()
  })

  it('picks the level by the cost of experiments a coarser level makes cheaper', () => {
    const large: ExperimentMetricCatalog = {
      ...rev3,
      metrics: [entry('loss', 0, 10 * MILLION - 1)],
    }
    const raw: ExperimentMetricCatalog = { ...rev2, metrics: [entry('loss', 0, 5 * MILLION - 1)] }
    const plan = planBucketRead(
      new Map([
        ['new', large],
        ['old', raw],
      ]),
      { modelIds: ['new', 'old'], keys: ['loss'], bucketBudget: 1000 },
      new BucketCache(),
    )

    expect(plan).toMatchObject({ level: 7, requestedLevel: 7, degraded: false, overBudget: true })
  })

  it('returns no plan for a range that holds no integer step', () => {
    for (const [startStep, endStep] of [
      [10.2, 10.8],
      [5, 4],
    ]) {
      expect(
        planBucketRead(
          new Map([['new', rev3]]),
          { ...whole, startStep, endStep },
          new BucketCache(),
        ),
      ).toBeNull()
    }
  })

  it('reads keys of five different lengths with one query per experiment', () => {
    const lengths: ExperimentMetricCatalog = {
      ...rev3,
      metrics: [10, 1000, 50_000, 200_000, MILLION].map((length, index) =>
        entry(`k${index}`, index * 7, length - 1),
      ),
    }
    const plan = planBucketRead(
      new Map([
        ['a', lengths],
        ['b', { ...lengths, revision: 2, bucket_min_level: null, bucket_max_level: null }],
      ]),
      { modelIds: ['a', 'b'], keys: ['k0', 'k1', 'k2', 'k3', 'k4'], bucketBudget: 1000 },
      new BucketCache(),
      { localModelIds: new Set(['a', 'b']) },
    )

    expect(plan?.experiments.map((experiment) => experiment.fetches)).toEqual([
      [
        {
          keys: ['k0', 'k1', 'k2', 'k3', 'k4'],
          firstBucket: 0,
          lastBucket: 976,
          startStep: 0,
          endStep: 1_000_447,
        },
      ],
      [
        {
          keys: ['k0', 'k1', 'k2', 'k3', 'k4'],
          firstBucket: 0,
          lastBucket: 976,
          startStep: 0,
          endStep: 1_000_447,
        },
      ],
    ])
  })
})
