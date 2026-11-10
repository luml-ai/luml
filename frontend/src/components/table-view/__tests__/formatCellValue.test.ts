import { describe, it, expect } from 'vitest'
import { formatCellValue } from '../index.vue'
import { DataTableArquero } from '@/lib/data-table/DataTableArquero'

describe('formatCellValue', () => {
  it('renders local-midnight dates as a bare day', () => {
    expect(formatCellValue(new Date('2020-01-01T00:00:00'))).toBe('2020-01-01')
  })

  it('renders intraday dates with their time', () => {
    expect(formatCellValue(new Date('2020-01-01T13:45:00'))).toBe('2020-01-01 13:45')
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

  it('preserves date-only CSV days alongside offset-less datetimes', async () => {
    const table = new DataTableArquero()
    await table.createFormCSV({
      name: 'dates.csv',
      size: 100,
      text: async () => 'date\n2024-01-01\n2024-01-01T20:00\n2024-01-01T00:00\n2023-12-31T19:00',
    } as File)

    const dates = table.getObjects().map((row) => (row as { date: Date }).date)
    expect(dates.map(formatCellValue)).toEqual([
      '2024-01-01',
      '2024-01-01 20:00',
      '2024-01-01',
      '2023-12-31 19:00',
    ])
    expect(dates[0].toISOString()).toBe('2024-01-01T00:00:00.000Z')
  })
})

it('keeps offset-less late evening and midnight values in their original day', () => {
  expect(formatCellValue(new Date(2024, 0, 1, 20))).toBe('2024-01-01 20:00')
  expect(formatCellValue(new Date(2024, 0, 1))).toBe('2024-01-01')
})
