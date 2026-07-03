import { describe, it, expect } from 'vitest'
import {
  detectDateColumns,
  isDateColumn,
  isDateLike,
  lastDate,
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
