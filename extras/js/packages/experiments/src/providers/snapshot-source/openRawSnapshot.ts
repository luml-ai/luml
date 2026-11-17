import { DEFAULT_RANGE_CACHE_OPTIONS, type RangeCacheOptions } from './RangeChunkCache'
import type { RangeSqliteEngine } from './RangeSqliteEngine'
import type { SnapshotDatabase } from './SnapshotDatabase'
import {
  BufferRangeFile,
  downloadSnapshotMember,
  HttpRangeFile,
  probeSnapshotHeader,
  type SnapshotTransport,
} from './httpSource'
import { SQLITE_HEADER_SIZE, validateSqliteHeader } from './sqliteHeader'
import { assertSourceHeaders, type SnapshotSourceLocation } from './sourceLocation'

export type SnapshotTransportKind = 'zip-full' | 'raw-full' | 'raw-range'

/**
 * Why a range source was loaded whole: the storage ignored Range at open. A member above the
 * full-download cap does not open; init fails with `SnapshotSourceTooLargeError`.
 */
export type SnapshotTransportFallback = 'range-ignored'

/** `offset` and `size` locate the database member inside the artifact. */
export type RangeSnapshotSource = SnapshotSourceLocation & {
  kind: 'range'
  offset: number
  size: number
}

export type ExperimentSnapshotSource =
  | { kind: 'zip'; buffer: ArrayBuffer }
  | { kind: 'raw'; buffer: ArrayBuffer }
  | RangeSnapshotSource

export type RawSnapshotSource = Exclude<ExperimentSnapshotSource, { kind: 'zip' }>

export interface RawSnapshotOptions {
  maxFullDownloadBytes: number
  cache: Partial<RangeCacheOptions>
}

export const DEFAULT_RAW_SNAPSHOT_OPTIONS: RawSnapshotOptions = {
  maxFullDownloadBytes: 1024 * 1024 * 1024,
  cache: {},
}

export interface OpenedRawSnapshot {
  database: SnapshotDatabase
  transport: Exclude<SnapshotTransportKind, 'zip-full'>
  fallback: SnapshotTransportFallback | null
  rangeFile: HttpRangeFile | null
}

export function rangeSourceLocation(source: RangeSnapshotSource): SnapshotSourceLocation {
  const { url, headers, credentials } = source
  assertSourceHeaders(headers)
  return { url, ...(headers ? { headers } : {}), ...(credentials ? { credentials } : {}) }
}

function openInMemory(
  engine: RangeSqliteEngine,
  modelId: string,
  bytes: Uint8Array,
  fallback: SnapshotTransportFallback | null,
): OpenedRawSnapshot {
  validateSqliteHeader(modelId, bytes.subarray(0, SQLITE_HEADER_SIZE), bytes.length)
  return {
    database: engine.openDatabase(new BufferRangeFile(bytes)),
    transport: 'raw-full',
    fallback,
    rangeFile: null,
  }
}

export async function openRawSnapshot(
  engine: RangeSqliteEngine,
  transport: SnapshotTransport,
  modelId: string,
  source: RawSnapshotSource,
  options: RawSnapshotOptions,
  signal?: AbortSignal,
): Promise<OpenedRawSnapshot> {
  if (source.kind === 'raw') {
    return openInMemory(engine, modelId, new Uint8Array(source.buffer), null)
  }
  signal?.throwIfAborted()

  const location = rangeSourceLocation(source)
  const chunkSize = options.cache.chunkSize ?? DEFAULT_RANGE_CACHE_OPTIONS.chunkSize
  const probe = await probeSnapshotHeader(
    transport,
    modelId,
    location,
    source.offset,
    source.size,
    chunkSize,
    signal,
  )
  if (probe.rangeIgnored) {
    const bytes = await downloadSnapshotMember(
      transport,
      modelId,
      location,
      source.offset,
      source.size,
      options.maxFullDownloadBytes,
      signal,
    )
    return openInMemory(engine, modelId, bytes, 'range-ignored')
  }
  signal?.throwIfAborted()
  validateSqliteHeader(modelId, probe.header, source.size)
  const rangeFile = new HttpRangeFile(
    modelId,
    location,
    source.offset,
    source.size,
    transport.readRangeSync,
    options.cache,
  )
  rangeFile.seed(probe.header)
  return {
    database: engine.openDatabase(rangeFile),
    transport: 'raw-range',
    fallback: null,
    rangeFile,
  }
}
