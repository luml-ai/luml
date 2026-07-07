import { describe, it, expect } from 'vitest'
import {
  cutStringOnMiddle,
  getFormattedExecutionTime,
  getFormattedTime,
} from '@/helpers/helpers'

describe('cutStringOnMiddle', () => {
  it('returns the string unchanged when shorter than the limit', () => {
    expect(cutStringOnMiddle('short', 20)).toBe('short')
  })

  it('truncates a long string with an ellipsis in the middle', () => {
    expect(cutStringOnMiddle('abcdefghij', 6)).toBe('abc...hij')
  })
})

describe('getFormattedExecutionTime', () => {
  describe('sub-microsecond floor', () => {
    // Scenario: sub-microsecond and negative durations display as a floor.
    it.each([
      [500, '<1µs'],
      [0, '<1µs'],
      [-256, '<1µs'],
      [999, '<1µs'],
      [-1_000_000, '<1µs'],
    ])('formats %ins as %s (never a raw or negative value)', (ns, expected) => {
      expect(getFormattedExecutionTime(ns)).toBe(expected)
    })
  })

  describe('microsecond tier', () => {
    // Scenario: microsecond-range span no longer shows 0ms.
    it('formats 40,000ns as 40µs, not 0ms', () => {
      expect(getFormattedExecutionTime(40_000)).toBe('40µs')
    })

    it.each([
      [1_000, '1µs'],
      [42_000, '42µs'],
      [999_000, '999µs'],
      [999_499, '999µs'],
    ])('formats %ins as %s', (ns, expected) => {
      expect(getFormattedExecutionTime(ns)).toBe(expected)
    })

    // Scenario: fractional nanosecond input is handled.
    it('handles fractional nanosecond input without leaking fractions', () => {
      expect(getFormattedExecutionTime(1234.56)).toBe('1µs')
    })
  })

  describe('millisecond tier', () => {
    it.each([
      [1_000_000, '1ms'],
      [500_000_000, '500ms'],
      [999_000_000, '999ms'],
    ])('formats %ins as %s', (ns, expected) => {
      expect(getFormattedExecutionTime(ns)).toBe(expected)
    })
  })

  describe('second tier and above', () => {
    // Scenario: normal tiers are preserved.
    it.each([
      [500_000_000, '500ms'],
      [5_400_000_000, '5.40s'],
      [90_000_000_000, '1min 30s'],
    ])('formats %ins as %s', (ns, expected) => {
      expect(getFormattedExecutionTime(ns)).toBe(expected)
    })

    it.each([
      [1_000_000_000, '1.00s'],
      [59_940_000_000, '59.94s'],
      [3_600_000_000_000, '1h 0min'],
      [3_660_000_000_000, '1h 1min'],
      [86_400_000_000_000, '1d 0h'],
      [90_000_000_000_000, '1d 1h'],
    ])('formats %ins as %s', (ns, expected) => {
      expect(getFormattedExecutionTime(ns)).toBe(expected)
    })
  })

  describe('tier-boundary artifacts', () => {
    // Scenario: no tier-boundary artifacts — rounding at an edge promotes up.
    it.each([
      [999_999, '1ms'],
      [999_600_000, '1.00s'],
      [59_999_000_000, '1min 0s'],
    ])('formats %ins as %s instead of a boundary artifact', (ns, expected) => {
      expect(getFormattedExecutionTime(ns)).toBe(expected)
    })

    it('never renders 1000µs', () => {
      expect(getFormattedExecutionTime(999_999)).not.toContain('1000µs')
    })

    it('never renders 1000ms', () => {
      expect(getFormattedExecutionTime(999_600_000)).not.toContain('1000ms')
    })

    it('never renders 60.00s', () => {
      expect(getFormattedExecutionTime(59_999_000_000)).not.toContain('60.00s')
    })

    it('promotes minute-boundary values to the hour tier without a 60min artifact', () => {
      expect(getFormattedExecutionTime(3_599_700_000_000)).toBe('1h 0min')
    })

    it('promotes hour-boundary values to the day tier without a 24h artifact', () => {
      expect(getFormattedExecutionTime(86_370_000_000_000)).toBe('1d 0h')
    })
  })
})

describe('getFormattedTime', () => {
  it('formats the difference between end and start nanoseconds', () => {
    expect(getFormattedTime(1_000, 41_000)).toBe('40µs')
    expect(getFormattedTime(0, 500_000_000)).toBe('500ms')
  })

  it('floors a zero-length span to <1µs', () => {
    expect(getFormattedTime(5_000, 5_000)).toBe('<1µs')
  })

  it('floors a negative float-rounding artifact to <1µs, never a negative value', () => {
    expect(getFormattedTime(1_000, 744)).toBe('<1µs')
  })
})
