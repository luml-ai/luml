import { InvalidBucketLevelError } from './errors'

/** Server-side and provider-side cap on the buckets one series may return. */
export const MAX_RETURNED_BUCKETS = 20_000

/** The contract's highest level; level 27 already covers every safe-integer step in one bucket. */
export const MAX_BUCKET_LEVEL = 31

function assertSafeStep(name: string, step: number): void {
  if (!Number.isSafeInteger(step)) throw new RangeError(`${name} must be a safe integer`)
}

export function assertBucketLevel(level: number): void {
  if (!Number.isInteger(level) || level < 0 || level > MAX_BUCKET_LEVEL) {
    throw new InvalidBucketLevelError(level, MAX_BUCKET_LEVEL)
  }
}

/**
 * The smallest level >= 0 with `ceil((lastStep - firstStep + 1) / 4^level) <= maxBuckets`.
 * Computed in BigInt: the span of two safe-integer steps can exceed 2^53.
 */
export function chooseBucketLevel(firstStep: number, lastStep: number, maxBuckets: number): number {
  assertSafeStep('firstStep', firstStep)
  assertSafeStep('lastStep', lastStep)
  if (!Number.isInteger(maxBuckets) || maxBuckets < 1) {
    throw new RangeError('maxBuckets must be a positive integer')
  }
  if (lastStep < firstStep) throw new RangeError('lastStep must not be smaller than firstStep')
  const span = BigInt(lastStep) - BigInt(firstStep) + 1n
  const budget = BigInt(maxBuckets)
  let level = 0
  let width = 1n
  while ((span + width - 1n) / width > budget) {
    level++
    width *= 4n
  }
  return level
}

/** Floor division by 4^level, right for negative steps; exact because 4^level is a power of two. */
export function bucketOf(step: number, level: number): number {
  return Math.floor(step / 4 ** level)
}

const MAX_SAFE = BigInt(Number.MAX_SAFE_INTEGER)

function clampSafe(step: bigint): number {
  return Number(step < -MAX_SAFE ? -MAX_SAFE : step > MAX_SAFE ? MAX_SAFE : step)
}

/**
 * The inclusive step range of buckets `[firstBucket, lastBucket]`, clamped to safe integers
 * (steps never leave that range). Computed in BigInt: from level 27 on `4^level - 1` is not
 * a double, and rounding it would move the range's end into the next bucket.
 */
export function bucketStepRange(
  firstBucket: number,
  lastBucket: number,
  level: number,
): [number, number] {
  const shift = BigInt(2 * level)
  return [
    clampSafe(BigInt(firstBucket) << shift),
    clampSafe(((BigInt(lastBucket) + 1n) << shift) - 1n),
  ]
}
