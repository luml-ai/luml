import { describe, it, expect, afterEach } from 'vitest'
import {
  detectDateColumns,
  generateForecastDates,
  isDateColumn,
  isDateLike,
  isNumericColumn,
  lastDate,
  periodKey,
  periodsBetween,
  toUtcDay,
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

  it('reports at least one period for a later date inside the same period', () => {
    expect(periodsBetween(new Date('2020-01-15'), new Date('2020-01-20'), 'month')).toBe(1)
  })

  it('counts period boundaries regardless of either date`s day of month', () => {
    // The engine snaps month/quarter/year forecasts to the period start, so
    // the horizon must not depend on the (arbitrary) day of the last history
    // row after aggregation.
    expect(periodsBetween(new Date('2020-01-01'), new Date('2020-02-28'), 'month')).toBe(1)
    expect(periodsBetween(new Date('2020-01-31'), new Date('2020-02-28'), 'month')).toBe(1)
    expect(periodsBetween(new Date('2020-01-01'), new Date('2020-03-01'), 'month')).toBe(2)
    expect(periodsBetween(new Date('2020-01-15'), new Date('2020-06-10'), 'quarter')).toBe(1)
    expect(periodsBetween(new Date('2020-06-01'), new Date('2021-12-15'), 'year')).toBe(1)
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

describe('isNumericColumn', () => {
  it('accepts number and numeric-string columns', () => {
    const rows = [
      { n: 1, s: '10.5', d: new Date('2020-01-01'), t: 'north' },
      { n: 2.5, s: '-3', d: new Date('2020-02-01'), t: 'south' },
    ]
    expect(isNumericColumn(rows, 'n')).toBe(true)
    expect(isNumericColumn(rows, 's')).toBe(true)
  })

  it('rejects text, date, and empty columns', () => {
    const rows = [
      { d: new Date('2020-01-01'), t: 'north', e: null },
      { d: new Date('2020-02-01'), t: 'south', e: '' },
    ]
    expect(isNumericColumn(rows, 't')).toBe(false)
    expect(isNumericColumn(rows, 'd')).toBe(false)
    expect(isNumericColumn(rows, 'e')).toBe(false)
  })
})

describe('toUtcDay', () => {
  it('passes exact UTC midnights through untouched', () => {
    const utcMidnight = new Date('2020-03-01T00:00:00Z')
    expect(toUtcDay(utcMidnight)).toBe(utcMidnight)
  })

  it('truncates intraday timestamps to their UTC day', () => {
    // In a UTC test runner local time == UTC; the timezone-sensitive branch is
    // covered by the timezone-independence suite below.
    expect(toUtcDay(new Date('2020-03-01T15:30:00Z')).toISOString()).toBe(
      '2020-03-01T00:00:00.000Z',
    )
  })
})

// Node re-reads process.env.TZ on date operations, so these run the same
// parsing paths a browser in that zone would. Etc/GMT signs are inverted:
// Etc/GMT-14 is UTC+14 (Kiritimati), Etc/GMT+12 is UTC-12.
describe.each(['Etc/GMT-14', 'Etc/GMT+12'])('timezone independence (%s)', (tz) => {
  const originalTZ = process.env.TZ

  afterEach(() => {
    if (originalTZ === undefined) delete process.env.TZ
    else process.env.TZ = originalTZ
  })

  it('buckets non-ISO date strings into the calendar period the user sees', () => {
    process.env.TZ = tz
    // Date.parse reads "02/01/2020" as local midnight; without UTC re-anchoring
    // the month key would shift to 2020-01 east of UTC.
    expect(periodKey('02/01/2020', 'month')).toBe('2020-02')
    expect(periodKey('02/01/2020', 'day')).toBe('2020-02-01')
    expect(periodKey('Mar 31, 2020', 'quarter')).toBe('2020-Q1')
  })

  it('anchors lastDate for non-ISO strings to UTC midnight of the visible day', () => {
    process.env.TZ = tz
    const rows = [{ date: '01/31/2020' }, { date: '01/15/2020' }]
    expect(lastDate(rows, 'date')?.toISOString()).toBe('2020-01-31T00:00:00.000Z')
  })

  it('computes exact day horizons from local-midnight picker dates', () => {
    process.env.TZ = tz
    const from = new Date('2020-01-31') // ISO date-only: UTC midnight
    const picked = new Date(2020, 1, 5) // DatePicker yields local midnight
    expect(periodsBetween(from, picked, 'day')).toBe(5)
    expect(periodsBetween(from, picked, 'month')).toBe(1)
  })

  it('generates the same forecast grid the engine will validate against', () => {
    process.env.TZ = tz
    const from = lastDate([{ date: '12/31/2020' }], 'date')
    expect(from).not.toBeNull()
    expect(generateForecastDates(from as Date, 2, 'month')).toEqual(['2021-01-01', '2021-02-01'])
    expect(generateForecastDates(from as Date, 2, 'day')).toEqual(['2021-01-01', '2021-01-02'])
  })
})
