import { describe, expect, it } from 'vitest'

import { fixNumber, getFormattedMetric } from '../helpers'

describe('getFormattedMetric', () => {
  it('keeps a genuine zero distinct from missing metrics', () => {
    expect(getFormattedMetric(0)).toBe('0')
    expect(getFormattedMetric(null)).toBe('—')
    expect(getFormattedMetric(undefined)).toBe('—')
  })

  it('uses scientific notation when two decimals would hide a small metric', () => {
    expect(getFormattedMetric(0.004)).toBe('4E-3')
    expect(getFormattedMetric(0.0004)).toBe('4E-4')
    expect(getFormattedMetric(-0.004)).toBe('-4E-3')
  })

  it('retains the existing formatting for ordinary and large metrics', () => {
    expect(getFormattedMetric(0.42)).toBe('0.42')
    expect(getFormattedMetric(1234)).toBe('1234')
    expect(getFormattedMetric(1_000_000)).toBe('1E6')
  })
})

describe('fixNumber', () => {
  it('keeps a genuine zero distinct from missing metrics', () => {
    expect(fixNumber(0, 2)).toBe('0')
    expect(fixNumber(null, 2)).toBe('—')
    expect(fixNumber(undefined, 2)).toBe('—')
  })
})
