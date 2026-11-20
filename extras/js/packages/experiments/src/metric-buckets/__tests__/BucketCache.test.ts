import { describe, expect, it } from 'vitest'
import { BucketCache } from '../BucketCache'
import type { MetricBucket } from '../types'

function bucket(index: number): MetricBucket {
  return {
    bucket: index,
    first_step: index,
    last_step: index,
    count: 1,
    finite_count: 1,
    min: index,
    max: index,
    sum: index,
  }
}

const range = (first: number, last: number) =>
  Array.from({ length: last - first + 1 }, (_, offset) => bucket(first + offset))

describe('BucketCache', () => {
  it('answers what is missing per experiment, metric and level', () => {
    const cache = new BucketCache()
    cache.write('a', 'loss', 3, 0, 9, range(0, 9))
    cache.write('a', 'loss', 3, 10, 19, [])

    expect(cache.missing('a', 'loss', 3, -5, 25)).toEqual([
      [-5, -1],
      [20, 25],
    ])
    expect(cache.missing('a', 'loss', 4, 0, 1)).toEqual([[0, 1]])
    expect(cache.missing('b', 'loss', 3, 0, 1)).toEqual([[0, 1]])
    expect(cache.read('a', 'loss', 3, 5, 15).map((item) => item.bucket)).toEqual([5, 6, 7, 8, 9])
  })

  it('evicts the least recently used series-level beyond its bound', () => {
    const cache = new BucketCache({ maxBuckets: 25 })
    cache.write('a', 'loss', 3, 0, 9, range(0, 9))
    cache.write('b', 'loss', 3, 0, 9, range(0, 9))
    cache.read('a', 'loss', 3, 0, 9)
    cache.write('c', 'loss', 3, 0, 9, range(0, 9))

    expect(cache.covers('a', 'loss', 3, 0, 9)).toBe(true)
    expect(cache.covers('b', 'loss', 3, 0, 9)).toBe(false)
    expect(cache.covers('c', 'loss', 3, 0, 9)).toBe(true)
    expect(cache.bucketCount).toBe(20)
  })

  it('does not cache a write the bound cannot hold and changes nothing for it', () => {
    const cache = new BucketCache({ maxBuckets: 15 })
    expect(cache.write('a', 'loss', 3, 0, 9, range(0, 9))).toBe(true)
    expect(cache.write('a', 'loss', 3, 10, 29, range(10, 29))).toBe(false)

    expect(cache.coverage('a', 'loss', 3)).toEqual([[0, 9]])
    expect(cache.bucketCount).toBe(10)
  })

  it('never evicts a pinned series and rejects the write instead', () => {
    const cache = new BucketCache({ maxBuckets: 25 })
    cache.write('a', 'loss', 3, 0, 9, range(0, 9))
    cache.write('b', 'loss', 3, 0, 9, range(0, 9))
    cache.pin('a', 'loss', 3)
    cache.pin('b', 'loss', 3)
    cache.unpin('b', 'loss', 3)
    cache.pin('a', 'loss', 3)
    cache.unpin('a', 'loss', 3)

    expect(cache.write('c', 'loss', 3, 0, 9, range(0, 9))).toBe(true)
    expect(cache.covers('a', 'loss', 3, 0, 9)).toBe(true)
    expect(cache.covers('b', 'loss', 3, 0, 9)).toBe(false)
    cache.pin('c', 'loss', 3)
    expect(cache.write('d', 'loss', 3, 0, 9, range(0, 9))).toBe(false)
    expect(cache.bucketCount).toBe(20)
  })

  it('drops a whole metric at every level', () => {
    const cache = new BucketCache()
    cache.write('a', 'loss', 3, 0, 9, range(0, 9))
    cache.write('a', 'loss', 4, 0, 2, range(0, 2))
    cache.write('a', 'acc', 3, 0, 9, range(0, 9))
    cache.dropMetric('a', 'loss')

    expect(cache.missing('a', 'loss', 3, 0, 9)).toEqual([[0, 9]])
    expect(cache.missing('a', 'loss', 4, 0, 2)).toEqual([[0, 2]])
    expect(cache.covers('a', 'acc', 3, 0, 9)).toBe(true)
    expect(cache.bucketCount).toBe(10)
  })
})
