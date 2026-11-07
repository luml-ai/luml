import { describe, expect, it } from 'vitest'
import { dateToText } from './date'

describe('dateToText', () => {
  it.each([null, undefined, '', 'invalid'])(
    'renders missing or invalid dates as a dash: %s',
    (value) => {
      expect(dateToText(value)).toBe('-')
    },
  )
  it('formats a valid local date', () => {
    expect(dateToText('2026-10-07T12:34:56')).toBe('2026/10/07 12:34:56')
  })
})
