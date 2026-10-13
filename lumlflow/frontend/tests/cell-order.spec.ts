import { describe, expect, it } from 'vitest'

import { compareOrder } from '@/store/flow/order'

describe('cell order', () => {
  it('compares decimal orders by value, not by text', () => {
    const orders = ['10', '2', '1.5', '-1', '0.25', '-0.5', '1.50']

    expect([...orders].sort(compareOrder)).toEqual(['-1', '-0.5', '0.25', '1.5', '1.50', '2', '10'])
  })

  it('treats negative zero and padded zeros as equal', () => {
    expect(compareOrder('-0', '0')).toBe(0)
    expect(compareOrder('007.100', '7.1')).toBe(0)
  })
})
