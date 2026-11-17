import { describe, expect, it } from 'vitest'
import { RangeChunkCache } from '../snapshot-source/RangeChunkCache'

const KIB = 1024
const CHUNK = 64 * KIB

function patternBytes(size: number): Uint8Array {
  return Uint8Array.from({ length: size }, (_, index) => (index * 31 + 7) % 251)
}

function cacheOver(size: number, options: ConstructorParameters<typeof RangeChunkCache>[2] = {}) {
  const bytes = patternBytes(size)
  const calls: [number, number][] = []
  const cache = new RangeChunkCache(
    (offset, length) => {
      calls.push([offset, length])
      return bytes.slice(offset, offset + length)
    },
    size,
    { chunkSize: CHUNK, ...options },
  )
  return { bytes, calls, cache }
}

describe('RangeChunkCache', () => {
  it('returns exact bytes and fetches whole aligned chunks once', () => {
    const { bytes, calls, cache } = cacheOver(10 * CHUNK)

    expect(cache.read(CHUNK + 100, 50)).toEqual(bytes.slice(CHUNK + 100, CHUNK + 150))
    expect(cache.read(CHUNK + 4000, 16 * KIB)).toEqual(
      bytes.slice(CHUNK + 4000, CHUNK + 4000 + 16 * KIB),
    )
    expect(calls).toEqual([[CHUNK, CHUNK]])
    expect(cache.stats).toEqual({ requests: 1, bytesFetched: CHUNK, cacheHits: 1, cacheMisses: 1 })
  })

  it('serves seeded whole chunks without a request and ignores a partial one', () => {
    const { bytes, calls, cache } = cacheOver(10 * CHUNK)
    cache.seed(bytes.slice(0, CHUNK + 100))

    expect(cache.read(10, 100)).toEqual(bytes.slice(10, 110))
    expect(calls).toEqual([])
    cache.read(CHUNK + 10, 10)
    expect(calls).toEqual([[CHUNK, 2 * CHUNK]])

    const small = cacheOver(1000)
    small.cache.seed(small.bytes)
    expect(small.cache.read(900, 100)).toEqual(small.bytes.slice(900))
    expect(small.calls).toEqual([])
  })

  it('fills a one-chunk hole after a cached chunk in the same request', () => {
    const { bytes, calls, cache } = cacheOver(10 * CHUNK)
    cache.seed(bytes.slice(0, CHUNK))

    expect(cache.read(2 * CHUNK, 10)).toEqual(bytes.slice(2 * CHUNK, 2 * CHUNK + 10))
    cache.read(CHUNK, 10)
    cache.read(6 * CHUNK, 10)
    expect(calls).toEqual([
      [CHUNK, 2 * CHUNK],
      [6 * CHUNK, CHUNK],
    ])
    expect(cache.stats).toMatchObject({ requests: 2, cacheMisses: 2, cacheHits: 1 })
  })

  it('reads a range across chunks with one request for the missing run', () => {
    const { bytes, calls, cache } = cacheOver(10 * CHUNK)
    cache.read(5 * CHUNK, 10)
    calls.length = 0

    const offset = 3 * CHUNK + 10
    const length = 4 * CHUNK
    expect(cache.read(offset, length)).toEqual(bytes.slice(offset, offset + length))
    expect(calls).toEqual([
      [3 * CHUNK, 2 * CHUNK],
      [6 * CHUNK, 2 * CHUNK],
    ])
  })

  it('clamps reads at the end of the file and fetches the short last chunk exactly', () => {
    const size = 2 * CHUNK + 1000
    const { bytes, calls, cache } = cacheOver(size)

    expect(cache.read(2 * CHUNK + 900, 500)).toEqual(bytes.slice(2 * CHUNK + 900, size))
    expect(cache.read(size, 10)).toEqual(new Uint8Array(0))
    expect(calls).toEqual([[2 * CHUNK, 1000]])
  })

  it('doubles read-ahead on sequential misses up to the cap', () => {
    const { calls, cache } = cacheOver(64 * CHUNK, { maxReadAheadBytes: 8 * CHUNK })
    for (let offset = 0; offset < 64 * CHUNK; offset += 16 * KIB) cache.read(offset, 16 * KIB)

    expect(calls.map(([, length]) => length / CHUNK)).toEqual([1, 2, 3, 5, 9, 9, 9, 9, 9, 8])
    expect(cache.stats.bytesFetched).toBe(64 * CHUNK)
  })

  it('restarts read-ahead after a failed read so the retry asks only for what it needs', () => {
    const bytes = patternBytes(64 * CHUNK)
    const calls: [number, number][] = []
    let failNextLarge = true
    const cache = new RangeChunkCache(
      (offset, length) => {
        calls.push([offset, length])
        if (failNextLarge && length === 9 * CHUNK) {
          failNextLarge = false
          throw new DOMException('timeout', 'TimeoutError')
        }
        return bytes.slice(offset, offset + length)
      },
      bytes.length,
      { chunkSize: CHUNK, maxReadAheadBytes: 8 * CHUNK },
    )
    const readSequentially = (from: number, to: number) => {
      for (let offset = from; offset < to; offset += 16 * KIB) cache.read(offset, 16 * KIB)
    }

    expect(() => readSequentially(0, 64 * CHUNK)).toThrow('timeout')
    const failedAt = calls.at(-1)![0]
    readSequentially(failedAt, 64 * CHUNK)
    expect(cache.read(10 * CHUNK, 2 * CHUNK)).toEqual(bytes.slice(10 * CHUNK, 12 * CHUNK))

    expect(calls.map(([offset, length]) => [offset / CHUNK, length / CHUNK])).toEqual([
      [0, 1],
      [1, 2],
      [3, 3],
      [6, 5],
      [11, 9],
      [11, 1],
      [12, 2],
      [14, 3],
      [17, 5],
      [22, 9],
      [31, 9],
      [40, 9],
      [49, 9],
      [58, 6],
    ])
  })

  it('resets read-ahead on random access so point reads fetch single chunks', () => {
    const { calls, cache } = cacheOver(64 * CHUNK)
    for (const chunk of [40, 3, 17, 55, 9]) cache.read(chunk * CHUNK + 100, 16 * KIB)

    expect(calls).toEqual([40, 3, 17, 55, 9].map((chunk) => [chunk * CHUNK, CHUNK]))
  })

  it('ramps read-ahead separately for interleaved sequential streams', () => {
    const { calls, cache } = cacheOver(64 * CHUNK)
    for (let step = 0; step < 16; step++) {
      cache.read(step * CHUNK, 1)
      cache.read((32 + step) * CHUNK, 1)
    }

    expect(calls.map(([offset, length]) => [offset / CHUNK, length / CHUNK])).toEqual([
      [0, 1],
      [32, 1],
      [1, 2],
      [33, 2],
      [3, 3],
      [35, 3],
      [6, 5],
      [38, 5],
      [11, 9],
      [43, 9],
    ])
  })

  it('does not read ahead into chunks that are already cached', () => {
    const { calls, cache } = cacheOver(32 * CHUNK)
    cache.read(4 * CHUNK, 1)
    cache.read(0, 1)
    cache.read(CHUNK, 1)
    cache.read(3 * CHUNK, 1)

    expect(calls).toEqual([
      [4 * CHUNK, CHUNK],
      [0, CHUNK],
      [CHUNK, 2 * CHUNK],
      [3 * CHUNK, CHUNK],
    ])
  })

  it('evicts least recently used chunks beyond the memory bound', () => {
    const { calls, cache } = cacheOver(16 * CHUNK, { maxCacheBytes: 3 * CHUNK })
    for (const chunk of [0, 5, 10]) cache.read(chunk * CHUNK, 1)
    cache.read(0, 1)
    cache.read(14 * CHUNK, 1)

    expect(cache.cachedChunkCount).toBe(3)
    calls.length = 0
    cache.read(0, 1)
    cache.read(10 * CHUNK, 1)
    expect(calls).toEqual([])
    cache.read(5 * CHUNK, 1)
    expect(calls.map(([offset]) => offset)).toEqual([5 * CHUNK])
  })

  it('fails the read when the source returns fewer bytes than requested', () => {
    const cache = new RangeChunkCache(() => new Uint8Array(10), 4 * CHUNK, { chunkSize: CHUNK })

    expect(() => cache.read(0, 100)).toThrow(/short read/)
  })

  it('rejects chunk sizes that are not a multiple of the 16 KiB page', () => {
    expect(() => new RangeChunkCache(() => new Uint8Array(), 100, { chunkSize: 10_000 })).toThrow(
      RangeError,
    )
  })
})
