import {
  redactSecrets,
  SNAPSHOT_FORMAT,
  SNAPSHOT_RANGE_UNSUPPORTED,
  SNAPSHOT_SOURCE_EXPIRED,
  SNAPSHOT_SOURCE_PAGE,
  SNAPSHOT_SOURCE_REDIRECT,
  SNAPSHOT_SOURCE_TOO_LARGE,
  SNAPSHOT_TOO_LARGE_FOR_BROWSER,
} from '../providers/snapshot-source/errors'
import {
  INVALID_LEVEL,
  NEEDS_NEWER_READER,
  READ_FAILED,
  TIMED_OUT,
  TOO_MANY_BUCKETS,
  type ExperimentReadError,
  type ExperimentReadErrorCode,
} from './types'

/** The experiment's `min_reader_revision` is above every revision this viewer knows. */
export class SnapshotNeedsNewerReaderError extends Error {
  readonly code = NEEDS_NEWER_READER

  constructor(
    readonly modelId: string,
    readonly revision: number,
    readonly minReaderRevision: number,
    readonly knownRevision: number,
  ) {
    super(
      `Experiment '${modelId}' (schema revision ${revision}) needs a viewer that reads revision ` +
        `${minReaderRevision}; this viewer reads up to revision ${knownRevision}`,
    )
    this.name = 'SnapshotNeedsNewerReaderError'
  }
}

export class TooManyBucketsError extends Error {
  readonly code = TOO_MANY_BUCKETS

  constructor(
    readonly modelId: string,
    readonly key: string,
    readonly limit: number,
  ) {
    super(`Metric '${key}' of '${modelId}' would return more than ${limit} buckets`)
    this.name = 'TooManyBucketsError'
  }
}

export class InvalidBucketLevelError extends RangeError {
  readonly code = INVALID_LEVEL

  constructor(
    readonly level: number,
    readonly maxLevel: number,
  ) {
    super(`level must be an integer in [0, ${maxLevel}], got ${level}`)
    this.name = 'InvalidBucketLevelError'
  }
}

/** A metric request got no answer in time; the store stops waiting for it. */
export class MetricReadTimeoutError extends Error {
  readonly code = TIMED_OUT

  constructor(readonly timeoutMs: number) {
    super(`No answer within ${Math.round(timeoutMs / 1000)} s`)
    this.name = 'MetricReadTimeoutError'
  }
}

const KNOWN_CODES: ExperimentReadErrorCode[] = [
  NEEDS_NEWER_READER,
  TOO_MANY_BUCKETS,
  INVALID_LEVEL,
  TIMED_OUT,
  SNAPSHOT_SOURCE_EXPIRED,
  SNAPSHOT_RANGE_UNSUPPORTED,
  SNAPSHOT_SOURCE_REDIRECT,
  SNAPSHOT_SOURCE_TOO_LARGE,
  SNAPSHOT_TOO_LARGE_FOR_BROWSER,
  SNAPSHOT_SOURCE_PAGE,
  SNAPSHOT_FORMAT,
]

/** The plain-object form of any failure, its message cleared of URLs and credentials. */
export function toExperimentReadError(error: unknown): ExperimentReadError {
  const code = (error as { code?: unknown } | null)?.code
  const message = error instanceof Error ? error.message : String(error)
  return {
    code: KNOWN_CODES.find((known) => known === code) ?? READ_FAILED,
    message: redactSecrets(message),
  }
}
