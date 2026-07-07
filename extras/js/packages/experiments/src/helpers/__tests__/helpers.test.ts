import { describe, it, expect } from 'vitest'
import { cutStringOnMiddle } from '@/helpers/helpers'

describe('cutStringOnMiddle', () => {
  it('returns the string unchanged when shorter than the limit', () => {
    expect(cutStringOnMiddle('short', 20)).toBe('short')
  })

  it('truncates a long string with an ellipsis in the middle', () => {
    expect(cutStringOnMiddle('abcdefghij', 6)).toBe('abc...hij')
  })
})
