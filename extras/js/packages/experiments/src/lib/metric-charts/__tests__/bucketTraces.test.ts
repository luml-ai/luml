import { describe, expect, it } from 'vitest'
import type { ChartSeries, MetricCatalogs } from '@/metric-buckets/MetricBucketStore'
import type { MetricBucket } from '@/metric-buckets/types'
import {
  bucketBudgetForWidth,
  buildBucketTraces,
  catalogMetricEntries,
  hoverLabel,
  ISOLATED_MARKER_SIZE,
  LINE_HOVER_TEMPLATE,
  maxShownLevel,
  requestStepRange,
  traceUid,
  visibleValueRange,
  type ScatterTrace,
} from '../bucketTraces'

function bucket(overrides: Partial<MetricBucket> & { bucket: number }): MetricBucket {
  return {
    first_step: overrides.bucket * 4,
    last_step: overrides.bucket * 4 + 3,
    count: 4,
    finite_count: 4,
    min: 0,
    max: 4,
    sum: 8,
    ...overrides,
  }
}

function series(buckets: MetricBucket[], level = 1, modelId = 'm1', final = true): ChartSeries {
  return { modelId, key: 'loss', level, final, buckets }
}

const style = () => ({ name: 'Model A', color: '#abcdef' })

const label = (trace: ScatterTrace | undefined, index = 0) =>
  trace ? hoverLabel(trace, index) : null

function catalogsOf(list: { key: string; first_step: number; last_step: number }[][]) {
  const catalogs: MetricCatalogs = {
    catalogs: new Map(),
    errors: new Map(),
    localModelIds: new Set(),
    statuses: [],
  }
  for (const [index, metrics] of list.entries()) {
    catalogs.catalogs.set(`m${index}`, {
      revision: 3,
      bucket_min_level: null,
      bucket_max_level: null,
      skipped_rows: 0,
      metrics: metrics.map((metric) => ({ ...metric, count: 1, min: 0, max: 0 })),
    })
  }
  return catalogs
}

describe('bucketBudgetForWidth', () => {
  it('gives one bucket per pixel within a floor and a ceiling', () => {
    expect(bucketBudgetForWidth(800.7)).toBe(800)
    expect(bucketBudgetForWidth(0)).toBe(100)
    expect(bucketBudgetForWidth(10_000)).toBe(4000)
  })
})

describe('buildBucketTraces', () => {
  it('breaks the line at a bucket with no finite value instead of interpolating', () => {
    const traces = buildBucketTraces(
      [
        series([
          bucket({ bucket: 0 }),
          bucket({ bucket: 1, finite_count: 0, sum: null, min: null, max: null }),
          bucket({ bucket: 2 }),
        ]),
      ],
      style,
    )
    const line = traces.find((trace) => trace.uid === 'm1-line')
    expect(line?.y).toEqual([2, null, 2])
    expect(line?.connectgaps).toBe(false)
    const band = traces.find((trace) => trace.uid === 'm1-band')
    // One closed polygon per run of buckets with a value, separated by null.
    expect(band?.x).toEqual([0, 3, 3, 0, null, 8, 11, 11, 8])
    expect(band?.y).toEqual([4, 4, 0, 0, null, 4, 4, 0, 0])
    expect(band).toMatchObject({ fill: 'toself', fillcolor: 'rgba(171, 205, 239, 0.2)' })
    expect(band?.opacity).toBeUndefined()
  })

  it('steps the band over the steps of each bucket and splits it at gaps', () => {
    const empty = { finite_count: 0, sum: null, min: null, max: null }
    const [band] = buildBucketTraces(
      [
        series([
          bucket({ bucket: 0, min: 0, max: 4 }),
          bucket({ bucket: 1, min: 1, max: 5 }),
          bucket({ bucket: 2, ...empty }),
          bucket({ bucket: 3, ...empty }),
          bucket({ bucket: 4, min: 2, max: 3 }),
          bucket({ bucket: 5, min: -1, max: 6 }),
        ]),
      ],
      style,
    )
    expect(band?.x).toEqual([0, 3, 4, 7, 7, 4, 3, 0, null, 16, 19, 20, 23, 23, 20, 19, 16])
    expect(band?.y).toEqual([4, 4, 5, 5, 1, 1, 0, 0, null, 3, 3, 6, 6, -1, -1, 2, 2])
  })

  it('spans a bucket from its first to its last logged step, not the nominal width', () => {
    const [band] = buildBucketTraces(
      [series([bucket({ bucket: 0, first_step: 1, last_step: 2 }), bucket({ bucket: 1 })])],
      style,
    )
    expect(band?.x).toEqual([1, 2, 4, 7, 7, 4, 2, 1])
  })

  it('draws nothing for a bucket whose band is empty and splits the band there', () => {
    const [band] = buildBucketTraces(
      [
        series([
          bucket({ bucket: 0 }),
          bucket({ bucket: 1, min: 2, max: 2, sum: 8 }),
          bucket({ bucket: 2 }),
          bucket({ bucket: 4 }),
        ]),
      ],
      style,
    )
    expect(band?.x).toEqual([0, 3, 3, 0, null, 8, 11, 11, 8, null, 16, 19, 19, 16])
  })

  it('leaves values beyond 1e290 out of the band and the y-range, like infinities', () => {
    const shown = [
      series([
        bucket({ bucket: 0, min: -1e300, max: 1e300, count: 6, finite_count: 4, sum: 8 }),
        bucket({ bucket: 1, min: 1e300, max: 1e300, count: 2, finite_count: 0, sum: null }),
        bucket({ bucket: 2, min: 1, max: 3 }),
      ]),
    ]
    const [band, line] = buildBucketTraces(shown, style)
    expect(line?.y).toEqual([2, null, 2])
    expect(band?.x).toEqual([8, 11, 11, 8])
    expect(band?.y).toEqual([3, 3, 1, 1])
    expect(visibleValueRange(shown, { first: 0, last: 11 })).toEqual([1, 3])
    expect(label(line)).toContain('Contains non-finite or out-of-range values')
  })

  it('names the step of a single point, so a unified hover never shows a value without it', () => {
    const shown = series(
      [bucket({ bucket: 0, first_step: 38, last_step: 38, count: 1, finite_count: 1, sum: 3 })],
      0,
    )
    expect(label(buildBucketTraces([shown], style)[0])).toBe('<b>Model A</b>: 3 · step 38')
  })

  it('leaves infinities out of the band and says so in the tooltip', () => {
    const traces = buildBucketTraces(
      [
        series([
          bucket({ bucket: 0, min: -Infinity, max: Infinity, count: 6, finite_count: 4, sum: 8 }),
        ]),
      ],
      style,
    )
    const [band, line] = traces
    expect(band?.y).toEqual([])
    expect(label(line)).toBe(
      '<b>Model A</b>: 2<br>6 points · steps 0–3<br>Contains non-finite or out-of-range values',
    )
  })

  it('draws no band when every bucket holds one point, even above level 0', () => {
    const traces = buildBucketTraces(
      [series([bucket({ bucket: 0, count: 1, finite_count: 1, sum: 3, min: 3, max: 3 })], 3)],
      style,
    )
    expect(traces.map((trace) => trace.uid)).toEqual(['m1-line'])
    expect(label(traces[0])).toBe('<b>Model A</b>: 3 · step 0')
  })

  it('takes the name from the trace and builds hover data once per series', () => {
    const shown = series([bucket({ bucket: 0 }), bucket({ bucket: 1 })])
    const [first] = buildBucketTraces([shown], style).slice(-1)
    const [again] = buildBucketTraces([shown], () => ({ name: 'Renamed', color: '#000' })).slice(-1)

    expect(first?.hovertemplate).toBe(LINE_HOVER_TEMPLATE)
    expect(first?.customdata).toBe(again?.customdata)
    expect(label(first, 1)).toBe('<b>Model A</b>: 2<br>min 0 · max 4<br>4 points · steps 4–7')
    expect(label(again, 1)).toBe('<b>Renamed</b>: 2<br>min 0 · max 4<br>4 points · steps 4–7')
  })

  it('marks values that have no drawn neighbour, so they are visible', () => {
    const empty = { finite_count: 0, sum: null, min: null, max: null }
    const traces = buildBucketTraces(
      [
        series([
          bucket({ bucket: 0 }),
          bucket({ bucket: 1, ...empty }),
          bucket({ bucket: 2 }),
          bucket({ bucket: 3, ...empty }),
          bucket({ bucket: 4 }),
          bucket({ bucket: 5 }),
        ]),
      ],
      style,
    )
    const line = traces.at(-1)
    expect(line?.mode).toBe('lines+markers')
    const size = ISOLATED_MARKER_SIZE
    expect(line?.marker).toEqual({ color: '#abcdef', size: [size, 0, size, 0, 0, 0] })
  })

  it('draws a plain line without markers when no value is isolated', () => {
    const traces = buildBucketTraces(
      [series([bucket({ bucket: 0 }), bucket({ bucket: 1 })])],
      style,
    )
    expect(traces.at(-1)).toMatchObject({ mode: 'lines' })
    expect(traces.at(-1)?.marker).toBeUndefined()
  })

  it('rounds aggregated values in the tooltip and keeps exact ones at level 0', () => {
    const value = 1 / 3
    const aggregated = buildBucketTraces(
      [series([bucket({ bucket: 0, sum: value * 4, min: value, max: value })])],
      style,
    )
    expect(label(aggregated.at(-1))).toContain(': 0.333333<br>')
    const exact = buildBucketTraces(
      [
        series(
          [bucket({ bucket: 0, count: 1, finite_count: 1, sum: value, min: value, max: value })],
          0,
        ),
      ],
      style,
    )
    expect(label(exact[0])).toBe(`<b>Model A</b>: ${String(value)} · step 0`)
  })
})

describe('visibleValueRange', () => {
  it('covers only the buckets that overlap the visible steps', () => {
    const shown = [
      series([bucket({ bucket: 0, min: -5, max: 1 }), bucket({ bucket: 10, min: 100, max: 200 })]),
    ]
    expect(visibleValueRange(shown, { first: 0, last: 10 })).toEqual([-5, 1])
    expect(visibleValueRange(shown, { first: 0, last: 50 })).toEqual([-5, 200])
    expect(visibleValueRange(shown, { first: 1000, last: 2000 })).toBeNull()
  })
})

describe('requestStepRange', () => {
  it('rounds outward and clamps to the metric range', () => {
    expect(requestStepRange([10.2, 20.7], { first: 0, last: 100 })).toEqual({ first: 10, last: 21 })
    expect(requestStepRange([-50, 500], { first: 0, last: 100 })).toEqual({ first: 0, last: 100 })
  })
})

describe('maxShownLevel', () => {
  it('ignores series whose points are single logged values', () => {
    const single = bucket({ bucket: 0, count: 1, finite_count: 1, sum: 1 })
    expect(maxShownLevel([series([single], 5)])).toBeNull()
    expect(maxShownLevel([series([bucket({ bucket: 0 })], 2)])).toBe(2)
  })
})

describe('catalogMetricEntries', () => {
  it('deduplicates keys shared by experiments and spans their union range', () => {
    const entries = catalogMetricEntries(
      catalogsOf([
        [{ key: 'loss', first_step: 10, last_step: 50 }],
        [
          { key: 'loss', first_step: 0, last_step: 20 },
          { key: 'acc', first_step: 5, last_step: 5 },
        ],
      ]),
    )
    expect(entries).toEqual([
      { key: 'acc', range: { first: 5, last: 5 } },
      { key: 'loss', range: { first: 0, last: 50 } },
    ])
  })

  it('sorts numbered names naturally', () => {
    const entries = catalogMetricEntries(
      catalogsOf([
        ['layer_10', 'layer_2', 'layer_1'].map((key) => ({ key, first_step: 0, last_step: 1 })),
      ]),
    )
    expect(entries.map((entry) => entry.key)).toEqual(['layer_1', 'layer_2', 'layer_10'])
  })

  it('is empty for an empty catalog', () => {
    expect(catalogMetricEntries(catalogsOf([[]]))).toEqual([])
  })
})

describe('traceUid', () => {
  const pathId = '/home/user/my runs/exp.v2 ünïcode 🚀_x.luml'

  it('gives a uid that Plotly can use as a CSS class selector for a path-like model id', () => {
    const traces = buildBucketTraces([series([bucket({ bucket: 0 })], 1, pathId)], style)
    const root = document.createElement('div')
    for (const trace of traces) {
      expect(() => root.querySelector(`.cb${trace.uid}`)).not.toThrow()
    }
    expect(traces.map((trace) => trace.uid)).toEqual([
      traceUid(pathId, 'band'),
      traceUid(pathId, 'line'),
    ])
  })

  it('keeps distinct model ids distinct', () => {
    const ids = ['a/b', 'a_b', 'a_2f_b', 'a.b', 'a b', 'ab', 'a-b']
    const uids = new Set(ids.map((id) => traceUid(id, 'line')))
    expect(uids.size).toBe(ids.length)
  })

  it('leaves a UUID model id unchanged', () => {
    const id = '3f2a9c1e-7b4d-4e8a-9f10-2c3d4e5f6a7b'
    expect(traceUid(id, 'line')).toBe(`${id}-line`)
    expect(traceUid(id, 'band')).toBe(`${id}-band`)
  })
})
