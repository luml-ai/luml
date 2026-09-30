import { describe, expect, it } from 'vitest'
import { formatChartNumber } from './format'

describe('formatChartNumber', () => {
  it.each([
    [0.0004, '0'],
    [-0.0004, '0'],
    [-0, '0'],
    [0.0006, '0.001'],
    [0.29999999999999999, '0.3'],
    [0.5, '0.5'],
    [1.23456, '1.235'],
    [-1.23456, '-1.235'],
    [42, '42'],
    [1234567.89123, '1,234,567.891'],
    [999.9999, '1,000'],
    [null, '—'],
    [undefined, '—'],
    [NaN, '—'],
    [Infinity, '—'],
    [-Infinity, '—'],
  ])('formats %s as %s', (value, expected) => {
    expect(formatChartNumber(value)).toBe(expected)
  })

  it.each([
    [0.005, '0.5%'],
    [0.12345678, '12.346%'],
    [1, '100%'],
    [-0.125, '-12.5%'],
    [-0.000004, '0%'],
    [null, '—'],
  ])('converts ratio %s before rounding to %s', (value, expected) => {
    expect(formatChartNumber(value, { percent: true })).toBe(expected)
  })

  it.each([
    [12345.6789, '12.346K'],
    [-1234567.89, '-1.235M'],
    [10000, '10K'],
    [1000000000, '1B'],
    [0.50001, '0.5'],
  ])('keeps compact predictions readable: %s as %s', (value, expected) => {
    expect(formatChartNumber(value, { compact: true })).toBe(expected)
  })
})
