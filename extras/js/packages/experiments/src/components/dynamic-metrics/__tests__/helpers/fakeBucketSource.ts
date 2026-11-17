import { vi } from 'vitest'
import type { MetricBucketSource } from '@/metric-buckets/MetricBucketStore'
import type {
  ExperimentMetricCatalog,
  ExperimentResult,
  ExperimentSnapshotStatus,
  MetricBucket,
  MetricBucketsRequest,
  MetricBucketsResponse,
  MetricCatalogsRequest,
} from '@/metric-buckets/types'

export interface Point {
  step: number
  value: number | null
}

export type ExperimentPoints = Record<string, Point[]>

/** Steps `first..last` (inclusive, every `stride`), value from `valueOf`. */
export function points(
  first: number,
  last: number,
  valueOf: (step: number) => number | null = (step) => step,
  stride = 1,
): Point[] {
  const result: Point[] = []
  for (let step = first; step <= last; step += stride) result.push({ step, value: valueOf(step) })
  return result
}

function isSummable(value: number | null): value is number {
  return value !== null && Math.abs(value) <= 1e290
}

export function aggregate(
  series: Point[],
  level: number,
  start: number,
  end: number,
): MetricBucket[] {
  const width = 4 ** level
  const firstBucket = Math.floor(start / width)
  const lastBucket = Math.floor(end / width)
  const buckets = new Map<number, MetricBucket>()
  for (const { step, value } of [...series].sort((a, b) => a.step - b.step)) {
    const index = Math.floor(step / width)
    if (index < firstBucket || index > lastBucket) continue
    const bucket = buckets.get(index) ?? {
      bucket: index,
      first_step: step,
      last_step: step,
      count: 0,
      finite_count: 0,
      min: null,
      max: null,
      sum: null,
    }
    bucket.count++
    bucket.last_step = step
    if (value !== null) {
      bucket.min = bucket.min === null ? value : Math.min(bucket.min, value)
      bucket.max = bucket.max === null ? value : Math.max(bucket.max, value)
    }
    if (isSummable(value)) {
      bucket.finite_count++
      bucket.sum = (bucket.sum ?? 0) + value
    }
    buckets.set(index, bucket)
  }
  return [...buckets.values()]
}

function catalogOf(data: ExperimentPoints, skippedRows: number): ExperimentMetricCatalog {
  return {
    revision: 3,
    bucket_min_level: 3,
    bucket_max_level: 12,
    skipped_rows: skippedRows,
    metrics: Object.entries(data)
      .filter(([, series]) => series.length > 0)
      .map(([key, series]) => {
        const steps = series.map((point) => point.step)
        const values = series.flatMap((point) => (point.value === null ? [] : [point.value]))
        return {
          key,
          first_step: Math.min(...steps),
          last_step: Math.max(...steps),
          count: series.length,
          min: values.length ? Math.min(...values) : null,
          max: values.length ? Math.max(...values) : null,
        }
      }),
  }
}

interface Gate {
  promise: Promise<void>
  release: () => void
}

/** An in-memory provider; with `hold()`, bucket reads wait until `releaseAll()`. */
export class FakeBucketSource implements MetricBucketSource {
  bucketCalls: MetricBucketsRequest[] = []
  catalogCalls: (MetricCatalogsRequest | undefined)[] = []
  abortedCalls = 0
  catalogErrors = new Set<string>()
  /** Experiments whose bucket reads answer with an error. */
  bucketErrors = new Set<string>()
  statuses: Partial<Record<string, Partial<ExperimentSnapshotStatus>>> = {}
  skippedRows: Record<string, number> = {}
  /** Experiments read as revision 2: catalogs without count, min and max. */
  legacy = new Set<string>()
  private gates: Gate[] = []
  private holding = false

  constructor(public data: Record<string, ExperimentPoints>) {}

  hold(): void {
    this.holding = true
  }

  releaseAll(): void {
    this.holding = false
    for (const gate of this.gates.splice(0)) gate.release()
  }

  getExperimentStatuses = vi.fn(async (): Promise<ExperimentSnapshotStatus[]> => {
    return Object.keys(this.data).map((modelId) => ({
      modelId,
      revision: 3,
      transport: 'zip-full',
      transportFallback: null,
      unknownNewerRevision: false,
      skippedMetricRows: this.skippedRows[modelId] ?? 0,
      error: null,
      ...this.statuses[modelId],
    }))
  })

  getMetricCatalogs = vi.fn(
    async (
      request?: MetricCatalogsRequest,
    ): Promise<ExperimentResult<ExperimentMetricCatalog>[]> => {
      this.catalogCalls.push(request)
      return (request?.modelIds ?? Object.keys(this.data)).map((modelId) => {
        if (this.catalogErrors.has(modelId)) {
          return {
            modelId,
            ok: false,
            error: { code: 'needs-newer-reader', message: 'Needs a newer reader' },
          }
        }
        const value = catalogOf(this.data[modelId] ?? {}, this.skippedRows[modelId] ?? 0)
        if (this.legacy.has(modelId)) {
          Object.assign(value, { revision: 2, bucket_min_level: null, bucket_max_level: null })
          value.metrics = value.metrics.map((entry) => ({
            ...entry,
            count: null,
            min: null,
            max: null,
          }))
        }
        return { modelId, ok: true, value }
      })
    },
  )

  getMetricBuckets = vi.fn(
    async (
      request: MetricBucketsRequest,
      signal?: AbortSignal,
    ): Promise<ExperimentResult<MetricBucketsResponse>[]> => {
      this.bucketCalls.push(request)
      // Answer with the data as of the call, as a real read would.
      const snapshot = (request.modelIds ?? Object.keys(this.data)).map((modelId) => ({
        modelId,
        series: request.keys.map((key) => [...(this.data[modelId]?.[key] ?? [])]),
      }))
      if (this.holding) {
        let release = () => {}
        const promise = new Promise<void>((resolve) => (release = resolve))
        this.gates.push({ promise, release })
        await promise
      }
      if (signal?.aborted) {
        this.abortedCalls++
        throw new DOMException('Aborted', 'AbortError')
      }
      return snapshot.map(({ modelId, series }): ExperimentResult<MetricBucketsResponse> => {
        if (this.bucketErrors.has(modelId)) {
          return { modelId, ok: false, error: { code: 'read-failed', message: 'Read failed' } }
        }
        const value: MetricBucketsResponse = {
          level: request.level,
          series: request.keys.map((key, index) => {
            const own = series[index] ?? []
            const steps = own.map((point) => point.step)
            return {
              key,
              first_step: own.length ? Math.min(...steps) : null,
              last_step: own.length ? Math.max(...steps) : null,
              buckets: aggregate(
                own,
                request.level,
                request.start_step ?? Number.MIN_SAFE_INTEGER,
                request.end_step ?? Number.MAX_SAFE_INTEGER,
              ),
            }
          }),
        }
        return { modelId, ok: true, value }
      })
    },
  )
}
