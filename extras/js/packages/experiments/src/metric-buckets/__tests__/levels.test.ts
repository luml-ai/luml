import { describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { bucketOf, bucketStepRange, chooseBucketLevel } from '../levels'

interface LevelVector {
  first_step: number
  last_step: number
  max_buckets: number
  level?: number
  error?: true
}

const VECTORS_FILE = resolve(
  __dirname,
  '../../../../../../../sdk/python/sdk/tests/fixtures/experiment_snapshots/bucket_level_vectors.json',
)
const { vectors } = JSON.parse(readFileSync(VECTORS_FILE, 'utf-8')) as { vectors: LevelVector[] }

describe('chooseBucketLevel', () => {
  it('reads the shared vectors', () => {
    expect(vectors.length).toBeGreaterThan(20)
  })

  it.each(vectors)('$first_step..$last_step in $max_buckets buckets', (vector) => {
    const choose = () => chooseBucketLevel(vector.first_step, vector.last_step, vector.max_buckets)
    if (vector.error) expect(choose).toThrow(RangeError)
    else expect(choose()).toBe(vector.level)
  })
})

describe('bucket arithmetic', () => {
  it('floors negative steps like an arithmetic shift', () => {
    expect([-1, -64, -65, 0, 63, 64].map((step) => bucketOf(step, 3))).toEqual([
      -1, -1, -2, 0, 0, 1,
    ])
    expect(bucketOf(-1, 40)).toBe(-1)
  })

  it('maps bucket ranges back to whole, safe step ranges', () => {
    expect(bucketStepRange(-2, 1, 3)).toEqual([-128, 127])
    expect(bucketStepRange(-1, 0, 30)).toEqual([-Number.MAX_SAFE_INTEGER, Number.MAX_SAFE_INTEGER])
  })

  // 4^level - 1 is not a double from level 27 on; rounding it once ended bucket -1 at step 0.
  it('ends a negative bucket below zero at every level up to 31', () => {
    expect(bucketStepRange(-1, -1, 26)).toEqual([-(2 ** 52), -1])
    for (let level = 27; level <= 31; level++) {
      expect(bucketStepRange(-1, -1, level), `level ${level}`).toEqual([
        -Number.MAX_SAFE_INTEGER,
        -1,
      ])
      expect(bucketStepRange(0, 0, level), `level ${level}`).toEqual([0, Number.MAX_SAFE_INTEGER])
    }
    expect(bucketStepRange(-3, -2, 25)).toEqual([-3 * 2 ** 50, -(2 ** 50) - 1])
  })
})
