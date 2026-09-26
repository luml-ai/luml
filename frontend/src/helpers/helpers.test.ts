import { describe, expect, it } from 'vitest'
import { getSizeText } from './helpers'

describe('getSizeText', () => {
  it.each([
    [0, '0.00 B'],
    [999, '999.00 B'],
    [1000, '1.00 KB'],
    [999999, '1000.00 KB'],
    [1000000, '1.00 MB'],
    [999999999, '1000.00 MB'],
    [1000000000, '1.00 GB'],
    [2620000000, '2.62 GB'],
  ])('formats %i bytes as %s', (size, expected) => {
    expect(getSizeText(size)).toBe(expected)
  })
})
