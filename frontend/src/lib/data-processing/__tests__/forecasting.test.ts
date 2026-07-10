import { describe, it, expect } from 'vitest'
import { normalizeForecastRecords } from '../forecasting'
import type { ForecastPredictedRecord } from '../interfaces'

describe('normalizeForecastRecords', () => {
  it('pivots a univariate forecast into one target series carrying bounds', () => {
    const records: ForecastPredictedRecord[] = [
      {
        date: '2024-01-01',
        predicted_sales: 100,
        predicted_sales_lower: 90,
        predicted_sales_upper: 110,
      },
      {
        date: '2024-02-01',
        predicted_sales: 120,
        predicted_sales_lower: 105,
        predicted_sales_upper: 135,
      },
    ]

    const series = normalizeForecastRecords(records, 'date', 'sales')

    expect(Object.keys(series)).toEqual(['sales'])
    expect(series.sales).toEqual([
      { date: '2024-01-01', value: 100, lower: 90, upper: 110 },
      { date: '2024-02-01', value: 120, lower: 105, upper: 135 },
    ])
  })

  it('splits a two-stage forecast into target (with bounds) and point-only auxiliaries', () => {
    const records: ForecastPredictedRecord[] = [
      {
        date: '2024-01-01',
        predicted_revenue: 1000,
        predicted_revenue_lower: 900,
        predicted_revenue_upper: 1100,
        predicted_marketing_spend: 50,
        predicted_visitors: 300,
      },
    ]

    const series = normalizeForecastRecords(records, 'date', 'revenue')

    expect(series.revenue).toEqual([{ date: '2024-01-01', value: 1000, lower: 900, upper: 1100 }])
    expect(series.marketing_spend).toEqual([{ date: '2024-01-01', value: 50 }])
    expect(series.visitors).toEqual([{ date: '2024-01-01', value: 300 }])
    expect(series.marketing_spend[0]).not.toHaveProperty('lower')
    expect(series.visitors[0]).not.toHaveProperty('upper')
  })

  it('omits known-future columns because the records never carry them', () => {
    const records: ForecastPredictedRecord[] = [
      {
        date: '2024-01-01',
        predicted_sales: 100,
        predicted_sales_lower: 90,
        predicted_sales_upper: 110,
        predicted_visitors: 40,
      },
    ]

    const series = normalizeForecastRecords(records, 'date', 'sales')

    expect(Object.keys(series).sort()).toEqual(['sales', 'visitors'])
    expect(series).not.toHaveProperty('promo')
  })

  it('never emits the target bound columns as their own series', () => {
    const records: ForecastPredictedRecord[] = [
      {
        date: '2024-01-01',
        predicted_sales: 100,
        predicted_sales_lower: 90,
        predicted_sales_upper: 110,
      },
    ]

    const series = normalizeForecastRecords(records, 'date', 'sales')

    expect(series).not.toHaveProperty('sales_lower')
    expect(series).not.toHaveProperty('sales_upper')
  })

  it('disambiguates an auxiliary whose name ends in _lower from the target bounds', () => {
    const records: ForecastPredictedRecord[] = [
      {
        date: '2024-01-01',
        predicted_sales: 100,
        predicted_sales_lower: 90,
        predicted_sales_upper: 110,
        predicted_temp_lower: 5,
      },
    ]

    const series = normalizeForecastRecords(records, 'date', 'sales')

    expect(series.temp_lower).toEqual([{ date: '2024-01-01', value: 5 }])
    expect(series.sales[0]).toEqual({ date: '2024-01-01', value: 100, lower: 90, upper: 110 })
  })

  it('honours a custom date column name', () => {
    const records: ForecastPredictedRecord[] = [
      {
        ds: '2024-01-01',
        predicted_sales: 100,
        predicted_sales_lower: 90,
        predicted_sales_upper: 110,
      },
    ]

    const series = normalizeForecastRecords(records, 'ds', 'sales')

    expect(series.sales).toEqual([{ date: '2024-01-01', value: 100, lower: 90, upper: 110 }])
    expect(series).not.toHaveProperty('ds')
  })

  it('coerces the date value to a string', () => {
    const records: ForecastPredictedRecord[] = [{ date: 20240101, predicted_sales: 100 }]

    const series = normalizeForecastRecords(records, 'date', 'sales')

    expect(series.sales[0].date).toBe('20240101')
  })

  it('emits a target point without bounds when they are absent', () => {
    const records: ForecastPredictedRecord[] = [{ date: '2024-01-01', predicted_sales: 100 }]

    const series = normalizeForecastRecords(records, 'date', 'sales')

    expect(series.sales).toEqual([{ date: '2024-01-01', value: 100 }])
    expect(series.sales[0]).not.toHaveProperty('lower')
  })

  it('returns an empty object for no records', () => {
    expect(normalizeForecastRecords([], 'date', 'sales')).toEqual({})
  })

  it('accumulates multiple horizon points per series in order', () => {
    const records: ForecastPredictedRecord[] = [
      { date: '2024-01-01', predicted_sales: 1, predicted_visitors: 10 },
      { date: '2024-02-01', predicted_sales: 2, predicted_visitors: 20 },
      { date: '2024-03-01', predicted_sales: 3, predicted_visitors: 30 },
    ]

    const series = normalizeForecastRecords(records, 'date', 'sales')

    expect(series.sales.map((p) => p.value)).toEqual([1, 2, 3])
    expect(series.visitors.map((p) => p.date)).toEqual(['2024-01-01', '2024-02-01', '2024-03-01'])
  })
})
