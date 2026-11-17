import type { SnapshotErrorCode } from '../providers/snapshot-source/errors'
import type { SnapshotTransportFallback } from '../providers/snapshot-source/openRawSnapshot'

export type SnapshotTransportKindOrApi = 'zip-full' | 'raw-full' | 'raw-range' | 'api'

export const NEEDS_NEWER_READER = 'needs-newer-reader'
export const TOO_MANY_BUCKETS = 'too-many-buckets'
export const INVALID_LEVEL = 'invalid-level'
export const READ_FAILED = 'read-failed'
export const TIMED_OUT = 'timed-out'

/** The snapshot source codes say why a database-backed experiment could not be read. */
export type ExperimentReadErrorCode =
  | typeof NEEDS_NEWER_READER
  | typeof TOO_MANY_BUCKETS
  | typeof INVALID_LEVEL
  | typeof READ_FAILED
  | typeof TIMED_OUT
  | SnapshotErrorCode

/**
 * A per-experiment failure; a plain object so it crosses the worker boundary unchanged. The
 * message never holds a URL beyond its origin, a query string or a credential.
 */
export interface ExperimentReadError {
  code: ExperimentReadErrorCode
  message: string
}

/** One experiment's answer to a call that covers several experiments. */
export type ExperimentResult<T> =
  | { modelId: string; ok: true; value: T }
  | { modelId: string; ok: false; error: ExperimentReadError }

/** What the viewer knows about an opened experiment, for status display. */
export interface ExperimentSnapshotStatus {
  modelId: string
  /** Null until known (the API provider learns it from the catalog). */
  revision: number | null
  transport: SnapshotTransportKindOrApi
  /** Why a range source ended up loaded whole; null when it was not a fallback. */
  transportFallback: SnapshotTransportFallback | null
  /** The DB is newer than this viewer but allows it to read; read as the newest known revision. */
  unknownNewerRevision: boolean
  /** The catalog's `skipped_rows`; null until the catalog has been read. */
  skippedMetricRows: number | null
  /**
   * Set by the metric store: a catalog step is beyond +-(2^53 - 1), where steps arrive
   * rounded, so only the steps inside that range are drawn.
   */
  unsafeMetricSteps?: boolean
  /** Set by the metric store: a bucket answer of this session left out fractional steps. */
  fractionalMetricSteps?: boolean
  error: ExperimentReadError | null
}

/** `count`, `min` and `max` are null below revision 3, where only the (key, step) index is read. */
export interface MetricCatalogEntry {
  key: string
  first_step: number
  last_step: number
  count: number | null
  min: number | null
  max: number | null
}

export interface ExperimentMetricCatalog {
  revision: number
  bucket_min_level: number | null
  bucket_max_level: number | null
  /**
   * Legacy metric rows left out of catalog and buckets: a non-text key or a NULL, text or BLOB
   * step. Rows with a fractional REAL step are left out too but counted only for a key without
   * any integer step; the buckets count the others (`MetricBucketSeries.skipped_rows`).
   */
  skipped_rows: number
  metrics: MetricCatalogEntry[]
}

export interface MetricCatalogsRequest {
  /** Experiments to read; all loaded experiments when omitted. */
  modelIds?: string[]
  /**
   * Read the catalog again instead of answering from a cache, for live experiments. A
   * published snapshot never changes, so the database provider answers from its cache
   * anyway (a no-op by design); the API provider always asks the server.
   */
  refresh?: boolean
}

/** Aggregate of the points whose step falls in `[bucket * 4^level, (bucket + 1) * 4^level)`. */
export interface MetricBucket {
  bucket: number
  first_step: number
  last_step: number
  count: number
  /** Values numeric and within +-1e290; beyond that and +-inf count in count, min and max only. */
  finite_count: number
  min: number | null
  max: number | null
  /** Over the `finite_count` values; null exactly when it is 0. Average = sum / finite_count. */
  sum: number | null
}

export interface MetricBucketSeries {
  key: string
  /** The metric's whole range, not the requested one; null when the key has no points. */
  first_step: number | null
  last_step: number | null
  buckets: MetricBucket[]
  /**
   * Revisions 0-2: the key's rows with a fractional REAL step in the requested range (without
   * an end on an open side), left out of the buckets. Not part of the catalog's count. A lower
   * bound when the key's scan hit its row limit and the buckets come from integer steps alone.
   */
  skipped_rows: number
}

export interface MetricBucketsResponse {
  level: number
  series: MetricBucketSeries[]
}

export interface MetricBucketsRequest {
  /** Experiments to read; all loaded experiments when omitted. */
  modelIds?: string[]
  keys: string[]
  /** Inclusive; the metric's whole range on a side that is null or omitted. */
  start_step?: number | null
  end_step?: number | null
  level: number
}
