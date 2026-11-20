import { describe, expect, it } from 'vitest'
import { tableCellToString } from '../texts'

const expectation = (value: string | number | null, positive = 0, negative = 0, others = 0) => ({
  isExpectationColumn: true,
  total: positive + negative + (value === null ? 0 : 1) + others,
  positive,
  negative,
  value,
})

describe('tableCellToString', () => {
  it.each([
    ['a single false', expectation(null, 0, 1), 'False (1)'],
    ['a single true', expectation(null, 1, 0), 'True (1)'],
    ['mixed counts', expectation(null, 2, 3), 'True (2) False (3)'],
  ])('writes a boolean expectation as its table cell shows it: %s', (_name, cell, text) => {
    expect(tableCellToString(cell)).toBe(text)
  })

  it('writes the value of an expectation that has one, whatever its counts', () => {
    expect(tableCellToString(expectation('Paris'))).toBe('Paris')
    expect(tableCellToString(expectation('Paris', 1, 1, 2))).toBe('Paris')
    expect(tableCellToString(expectation(0))).toBe('0')
  })

  it('writes an expectation without values or counts as an empty cell', () => {
    expect(tableCellToString(expectation(null))).toBeNull()
  })

  it('writes the counts of a feedback cell', () => {
    const feedback = { isFeedbackColumn: true, positiveCount: 2, negativeCount: 0 }
    expect(tableCellToString(feedback)).toBe('2 positive, 0 negative')
  })
})
