import { describe, it, expect } from 'vitest'
import {
  detectDateColumns,
  generateForecastDates,
  isDateColumn,
  isDateLike,
  lastDate,
  periodKey,
  periodsBetween,
} from '../forecasting-setup'

describe('isDateLike', () => {
  it('accepts valid Date instances (arquero auto-types ISO columns to Date)', () => {
    expect(isDateLike(new Date('2020-01-01'))).toBe(true)
    expect(isDateLike(new Date('invalid'))).toBe(false)
  })

  it('accepts non-numeric parseable date strings', () => {
    expect(isDateLike('2020-01-01')).toBe(true)
    expect(isDateLike('01/15/2020')).toBe(true)
    expect(isDateLike('Jan 2020')).toBe(true)
  })

  it('rejects bare numbers so numeric feature columns are not seen as dates', () => {
    expect(isDateLike(1500)).toBe(false)
    expect(isDateLike('1500')).toBe(false)
    expect(isDateLike('3.14')).toBe(false)
  })

  it('rejects empty and unparseable values', () => {
    expect(isDateLike('')).toBe(false)
    expect(isDateLike('   ')).toBe(false)
    expect(isDateLike('not a date')).toBe(false)
    expect(isDateLike(null)).toBe(false)
    expect(isDateLike(undefined)).toBe(false)
  })
})

describe('isDateColumn', () => {
  const rows = [
    { date: new Date('2020-01-01'), sales: 1000, label: 'not a date' },
    { date: new Date('2020-02-01'), sales: 1100, label: 'nope' },
    { date: new Date('2020-03-01'), sales: 1200, label: 'still no' },
  ]

  it('is true for a column of dates', () => {
    expect(isDateColumn(rows, 'date')).toBe(true)
  })

  it('is false for numeric and text columns', () => {
    expect(isDateColumn(rows, 'sales')).toBe(false)
    expect(isDateColumn(rows, 'label')).toBe(false)
  })

  it('is false when the column has no present values', () => {
    expect(isDateColumn([{ date: '' }, { date: null }], 'date')).toBe(false)
  })
})

describe('detectDateColumns', () => {
  it('returns only date-like columns, preserving order', () => {
    const rows = [
      { id: 1, when: '2020-01-01', qty: 5 },
      { id: 2, when: '2020-01-02', qty: 6 },
    ]
    expect(detectDateColumns(rows, ['id', 'when', 'qty'])).toEqual(['when'])
  })

  it('returns an empty list when no column parses as dates', () => {
    const rows = [
      { a: 1, b: 2 },
      { a: 3, b: 4 },
    ]
    expect(detectDateColumns(rows, ['a', 'b'])).toEqual([])
  })
})

describe('lastDate', () => {
  it('returns the most recent parseable date regardless of row order', () => {
    const rows = [
      { date: '2020-03-01' },
      { date: '2020-01-01' },
      { date: '2020-05-01' },
      { date: '2020-02-01' },
    ]
    expect(lastDate(rows, 'date')).toEqual(new Date('2020-05-01'))
  })

  it('returns null when nothing parses', () => {
    expect(lastDate([{ date: 'x' }, { date: '' }], 'date')).toBeNull()
  })
})

describe('periodsBetween', () => {
  const last = new Date('2020-01-31T00:00:00Z')

  it('counts day and week steps', () => {
    expect(periodsBetween(last, new Date('2020-02-05T00:00:00Z'), 'day')).toBe(5)
    expect(periodsBetween(last, new Date('2020-02-14T00:00:00Z'), 'week')).toBe(2)
  })

  it('counts calendar month, quarter, and year steps', () => {
    expect(periodsBetween(new Date('2020-01-15'), new Date('2020-04-15'), 'month')).toBe(3)
    expect(periodsBetween(new Date('2020-01-15'), new Date('2020-10-15'), 'quarter')).toBe(3)
    expect(periodsBetween(new Date('2020-01-15'), new Date('2023-01-15'), 'year')).toBe(3)
  })

  it('rounds partial periods up so the horizon reaches the end date', () => {
    expect(periodsBetween(new Date('2020-01-15'), new Date('2020-01-20'), 'month')).toBe(1)
  })

  it('returns 0 when the end is not after the start', () => {
    expect(periodsBetween(last, last, 'day')).toBe(0)
    expect(periodsBetween(last, new Date('2020-01-01T00:00:00Z'), 'month')).toBe(0)
  })
})

describe('generateForecastDates', () => {
  it('advances day and week frequencies by fixed offsets from the last date', () => {
    expect(generateForecastDates(new Date('2020-01-31'), 2, 'day')).toEqual([
      '2020-02-01',
      '2020-02-02',
    ])
    expect(generateForecastDates(new Date('2020-01-01'), 2, 'week')).toEqual([
      '2020-01-08',
      '2020-01-15',
    ])
  })

  it('snaps month, quarter, and year frequencies to the period start', () => {
    expect(generateForecastDates(new Date('2020-03-15'), 3, 'month')).toEqual([
      '2020-04-01',
      '2020-05-01',
      '2020-06-01',
    ])
    expect(generateForecastDates(new Date('2020-02-15'), 2, 'quarter')).toEqual([
      '2020-04-01',
      '2020-07-01',
    ])
    expect(generateForecastDates(new Date('2020-06-01'), 2, 'year')).toEqual([
      '2021-01-01',
      '2022-01-01',
    ])
  })

  it('returns an empty list for a non-positive horizon', () => {
    expect(generateForecastDates(new Date('2020-01-01'), 0, 'month')).toEqual([])
  })
})

describe('periodKey', () => {
  it('buckets coarse frequencies so any date in the period matches', () => {
    expect(periodKey('2020-03-01', 'month')).toBe('2020-03')
    expect(periodKey('2020-03-31', 'month')).toBe('2020-03')
    expect(periodKey('2020-05-10', 'quarter')).toBe('2020-Q2')
    expect(periodKey('2020-11-30', 'year')).toBe('2020')
  })

  it('uses the exact date for day and week frequencies', () => {
    expect(periodKey('2020-03-15', 'day')).toBe('2020-03-15')
    expect(periodKey(new Date('2020-03-15'), 'week')).toBe('2020-03-15')
  })

  it('returns null for values that are not dates', () => {
    expect(periodKey('not a date', 'month')).toBeNull()
    expect(periodKey(1500, 'month')).toBeNull()
  })
})
