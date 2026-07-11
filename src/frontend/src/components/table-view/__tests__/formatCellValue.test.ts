import { describe, it, expect } from 'vitest'
import { formatCellValue } from '../index.vue'

describe('formatCellValue', () => {
  it('renders UTC-midnight dates as a bare day', () => {
    expect(formatCellValue(new Date('2020-01-01T00:00:00Z'))).toBe('2020-01-01')
  })

  it('renders intraday dates with their time', () => {
    expect(formatCellValue(new Date('2020-01-01T13:45:00Z'))).toBe('2020-01-01 13:45')
  })

  it('passes an Invalid Date through instead of throwing', () => {
    const invalid = new Date('not a date')
    expect(formatCellValue(invalid)).toBe(invalid)
  })

  it('passes non-date values through untouched', () => {
    expect(formatCellValue('2020-01-01')).toBe('2020-01-01')
    expect(formatCellValue(42)).toBe(42)
    expect(formatCellValue(null)).toBeNull()
  })
})
