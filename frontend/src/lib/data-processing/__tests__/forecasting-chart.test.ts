import { describe, it, expect } from 'vitest'
import { FORECAST_SEGMENT_COLORS, buildForecastSegments } from '../forecasting-chart'
import type { ForecastingChart } from '../interfaces'

const chart: ForecastingChart = {
  split_date: '2020-03-01',
  series: {
    sales: {
      actuals: [
        { date: '2020-01-01', value: 10 },
        { date: '2020-02-01', value: 12 },
        { date: '2020-03-01', value: 14 },
        { date: '2020-04-01', value: 16 },
      ],
      test_fit: [
        { date: '2020-03-01', value: 13, lower: 11, upper: 15 },
        { date: '2020-04-01', value: 15, lower: 13, upper: 17 },
      ],
    },
    visitors: {
      actuals: [
        { date: '2020-01-01', value: 100 },
        { date: '2020-02-01', value: 120 },
        { date: '2020-03-01', value: 140 },
      ],
    },
  },
}

const byRole = (segments: ReturnType<typeof buildForecastSegments>, column: string, role: string) =>
  segments.find((s) => s.column === column && s.role === role)

describe('buildForecastSegments segmentation', () => {
  it('splits actuals into train and test coloured segments around split_date', () => {
    const segments = buildForecastSegments(chart, { targetCol: 'sales' })

    const train = byRole(segments, 'sales', 'train')
    const test = byRole(segments, 'sales', 'test')

    expect(train?.color).toBe(FORECAST_SEGMENT_COLORS.train)
    expect(train?.data).toEqual([
      { x: '2020-01-01', y: 10 },
      { x: '2020-02-01', y: 12 },
    ])

    expect(test?.color).toBe(FORECAST_SEGMENT_COLORS.test)
    // the last train point is repeated so the coloured lines join with no gap
    expect(test?.data).toEqual([
      { x: '2020-02-01', y: 12 },
      { x: '2020-03-01', y: 14 },
      { x: '2020-04-01', y: 16 },
    ])
  })

  it('draws the out-of-sample test_fit dashed and marked in its own colour', () => {
    const segments = buildForecastSegments(chart, { targetCol: 'sales' })
    const fit = segments.find((s) => s.column === 'sales' && s.role === 'testFit' && !s.isBound)

    expect(fit?.color).toBe(FORECAST_SEGMENT_COLORS.testFit)
    expect(fit?.dashArray).toBeGreaterThan(0)
    expect(fit?.markerSize).toBeGreaterThan(0)
    expect(fit?.data).toHaveLength(2)
  })

  it('adds dotted confidence-bound lines from the test_fit bounds', () => {
    const segments = buildForecastSegments(chart, { targetCol: 'sales' })
    const bounds = segments.filter(
      (s) => s.column === 'sales' && s.role === 'testFit' && s.isBound,
    )

    expect(bounds).toHaveLength(2)
    expect(bounds[0].data).toEqual([
      { x: '2020-03-01', y: 11 },
      { x: '2020-04-01', y: 13 },
    ])
    expect(bounds[1].data).toEqual([
      { x: '2020-03-01', y: 15 },
      { x: '2020-04-01', y: 17 },
    ])
    expect(bounds.every((s) => s.width === 1 && s.dashArray > 0)).toBe(true)
  })

  it('draws no bounds when the points carry none', () => {
    const segments = buildForecastSegments(chart, { targetCol: 'sales' })
    expect(segments.find((s) => s.column === 'visitors' && s.isBound)).toBeUndefined()
  })

  it('emphasises the target with a thicker stroke than auxiliaries', () => {
    const segments = buildForecastSegments(chart, { targetCol: 'sales' })
    const target = byRole(segments, 'sales', 'train')
    const aux = byRole(segments, 'visitors', 'train')

    expect(target?.width).toBeGreaterThan(aux?.width ?? 0)
  })

  it('keeps all actuals in the train segment when there is no split_date', () => {
    const segments = buildForecastSegments(
      { split_date: null, series: chart.series },
      { targetCol: 'sales' },
    )

    expect(byRole(segments, 'sales', 'train')?.data).toHaveLength(4)
    expect(byRole(segments, 'sales', 'test')).toBeUndefined()
  })
})

describe('buildForecastSegments overlays', () => {
  it('appends the re-forecast prediction dashed in the forecast colour', () => {
    const segments = buildForecastSegments(chart, {
      targetCol: 'sales',
      prediction: {
        sales: [
          { date: '2020-05-01', value: 18, lower: 16, upper: 20 },
          { date: '2020-06-01', value: 20, lower: 18, upper: 22 },
        ],
      },
    })

    const prediction = segments.find(
      (s) => s.column === 'sales' && s.role === 'prediction' && !s.isBound,
    )
    expect(prediction?.color).toBe(FORECAST_SEGMENT_COLORS.forecast)
    expect(prediction?.dashArray).toBeGreaterThan(0)
    expect(prediction?.data).toEqual([
      { x: '2020-05-01', y: 18 },
      { x: '2020-06-01', y: 20 },
    ])

    const bounds = segments.filter(
      (s) => s.column === 'sales' && s.role === 'prediction' && s.isBound,
    )
    expect(bounds.map((s) => s.data)).toEqual([
      [
        { x: '2020-05-01', y: 16 },
        { x: '2020-06-01', y: 18 },
      ],
      [
        { x: '2020-05-01', y: 20 },
        { x: '2020-06-01', y: 22 },
      ],
    ])
  })

  it('draws supplied known-future values as a distinct marked segment', () => {
    const segments = buildForecastSegments(chart, {
      targetCol: 'sales',
      knownFutureCols: ['promo'],
      supplied: { promo: [{ date: '2020-05-01', value: 1 }] },
    })

    const supplied = byRole(segments, 'promo', 'supplied')
    expect(supplied).toBeDefined()
    expect(supplied?.markerSize).toBeGreaterThan(0)
  })
})
