import { IntervalSet, type Interval } from './IntervalSet'
import { bucketOf } from './levels'
import type { MetricBucket } from './types'

/** What the planner may ask of a cache; reading it never changes the cache. */
export interface BucketCacheView {
  /** Bucket ranges of `[firstBucket, lastBucket]` at `level` not fetched yet. */
  missing(
    modelId: string,
    key: string,
    level: number,
    firstBucket: number,
    lastBucket: number,
  ): Interval[]
}

export interface BucketCacheOptions {
  /**
   * Upper bound on cached buckets over all series. Least recently used series that are not
   * pinned go first; a write that would still exceed it is not cached.
   */
  maxBuckets: number
}

export const DEFAULT_BUCKET_CACHE_OPTIONS: BucketCacheOptions = { maxBuckets: 500_000 }

interface SeriesLevel {
  modelId: string
  key: string
  level: number
  fetched: IntervalSet
  buckets: Map<number, MetricBucket>
}

/**
 * Fetched buckets keyed by (experiment, metric, level). A fetched range records that every
 * bucket with points in it is cached, so a bucket missing from a fetched range has no points.
 */
export class BucketCache implements BucketCacheView {
  private readonly options: BucketCacheOptions
  private readonly series = new Map<string, SeriesLevel>()
  private readonly pins = new Map<string, number>()
  private cachedBuckets = 0

  constructor(options: Partial<BucketCacheOptions> = {}) {
    this.options = { ...DEFAULT_BUCKET_CACHE_OPTIONS, ...options }
  }

  get bucketCount(): number {
    return this.cachedBuckets
  }

  get seriesCount(): number {
    return this.series.size
  }

  missing(
    modelId: string,
    key: string,
    level: number,
    firstBucket: number,
    lastBucket: number,
  ): Interval[] {
    const entry = this.series.get(seriesId(modelId, key, level))
    if (!entry) return firstBucket <= lastBucket ? [[firstBucket, lastBucket]] : []
    return entry.fetched.missing(firstBucket, lastBucket)
  }

  covers(
    modelId: string,
    key: string,
    level: number,
    firstBucket: number,
    lastBucket: number,
  ): boolean {
    return this.missing(modelId, key, level, firstBucket, lastBucket).length === 0
  }

  /** Cached buckets in `[firstBucket, lastBucket]` by bucket index; marks the series used. */
  read(
    modelId: string,
    key: string,
    level: number,
    firstBucket: number,
    lastBucket: number,
  ): MetricBucket[] {
    const id = seriesId(modelId, key, level)
    const entry = this.series.get(id)
    if (!entry) return []
    this.series.delete(id)
    this.series.set(id, entry)
    return [...entry.buckets.values()]
      .filter((bucket) => bucket.bucket >= firstBucket && bucket.bucket <= lastBucket)
      .sort((left, right) => left.bucket - right.bucket)
  }

  /** The fetched ranges of one series-level, in ascending order. */
  coverage(modelId: string, key: string, level: number): readonly Interval[] {
    return this.series.get(seriesId(modelId, key, level))?.fetched.intervals ?? []
  }

  /**
   * Stores the answer of a fetch of `[firstBucket, lastBucket]`, evicting unpinned series
   * first. Returns false, changing nothing, when the bound cannot make room for it.
   */
  write(
    modelId: string,
    key: string,
    level: number,
    firstBucket: number,
    lastBucket: number,
    buckets: readonly MetricBucket[],
  ): boolean {
    const id = seriesId(modelId, key, level)
    const existing = this.series.get(id)
    const added = buckets.filter((bucket) => !existing?.buckets.has(bucket.bucket)).length
    if (!this.makeRoom(id, added)) return false
    const entry = existing ?? {
      modelId,
      key,
      level,
      fetched: new IntervalSet(),
      buckets: new Map<number, MetricBucket>(),
    }
    this.series.delete(id)
    this.series.set(id, entry)
    for (const bucket of buckets) entry.buckets.set(bucket.bucket, bucket)
    this.cachedBuckets += added
    entry.fetched.add(firstBucket, lastBucket)
    return true
  }

  /** Keeps a series-level from eviction until as many `unpin` calls; for open charts. */
  pin(modelId: string, key: string, level: number): void {
    const id = seriesId(modelId, key, level)
    this.pins.set(id, (this.pins.get(id) ?? 0) + 1)
  }

  unpin(modelId: string, key: string, level: number): void {
    const id = seriesId(modelId, key, level)
    const count = (this.pins.get(id) ?? 0) - 1
    if (count > 0) this.pins.set(id, count)
    else this.pins.delete(id)
  }

  /** Forgets every cached bucket and pin. */
  clear(): void {
    this.series.clear()
    this.pins.clear()
    this.cachedBuckets = 0
  }

  /** Forgets every cached bucket of a metric at every level. */
  dropMetric(modelId: string, key: string): void {
    for (const [id, entry] of this.series) {
      if (entry.modelId !== modelId || entry.key !== key) continue
      this.series.delete(id)
      this.cachedBuckets -= entry.buckets.size
    }
  }

  /**
   * Forgets, at every level, the buckets of a metric from the one holding `step` on: a live
   * experiment grew there, so those buckets may have been partial.
   */
  dropFrom(modelId: string, key: string, step: number): void {
    for (const entry of this.series.values()) {
      if (entry.modelId !== modelId || entry.key !== key) continue
      const first = bucketOf(step, entry.level)
      entry.fetched.removeFrom(first)
      for (const index of entry.buckets.keys()) {
        if (index < first) continue
        entry.buckets.delete(index)
        this.cachedBuckets--
      }
    }
  }

  private makeRoom(keptId: string, added: number): boolean {
    const target = this.options.maxBuckets - added
    const evictable = [...this.series].filter(([id]) => id !== keptId && !this.pins.has(id))
    const freeable = evictable.reduce((total, [, entry]) => total + entry.buckets.size, 0)
    if (this.cachedBuckets - freeable > target) return false
    for (const [id, entry] of evictable) {
      if (this.cachedBuckets <= target) break
      this.series.delete(id)
      this.cachedBuckets -= entry.buckets.size
    }
    return true
  }
}

function seriesId(modelId: string, key: string, level: number): string {
  return JSON.stringify([modelId, key, level])
}
