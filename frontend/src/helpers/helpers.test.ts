import { describe, expect, it } from 'vitest'
import { getSizeText } from './helpers'

describe('getSizeText', () => {
  it.each([
    [0, '0.00 B'],
    [999, '999.00 B'],
    [1000, '1.00 KB'],
    [999994, '999.99 KB'],
    [999995, '1.00 MB'],
    [999999, '1.00 MB'],
    [1000000, '1.00 MB'],
    [250000000, '250.00 MB'],
    [999999999, '1.00 GB'],
    [1000000000, '1.00 GB'],
    [1700000000, '1.70 GB'],
    [100000000000, '100.00 GB'],
    [999999999999, '1.00 TB'],
    [1500000000000, '1.50 TB'],
    [5000000000000, '5.00 TB'],
    [2000000000000000, '2000.00 TB'],
  ])('formats %i bytes as %s', (size, expected) => {
    expect(getSizeText(size)).toBe(expected)
  })
})
