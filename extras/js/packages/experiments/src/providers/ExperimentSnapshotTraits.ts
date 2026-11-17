import type { SnapshotDatabase as Database } from './snapshot-source/SnapshotDatabase'

/** Experiment DB schema revisions (SDK `exp_migrations`) this viewer knows how to read. */
export const KNOWN_SCHEMA_REVISIONS = [0, 1, 2, 3] as const

export const NEWEST_KNOWN_REVISION = Math.max(...KNOWN_SCHEMA_REVISIONS)

type KnownSchemaRevision = (typeof KNOWN_SCHEMA_REVISIONS)[number]

/** `dynamic-metrics`: one table of points (revisions 0-2). `metric-points`: keys, points and buckets. */
export type MetricLayout = 'dynamic-metrics' | 'metric-points'

export interface BucketLevelRange {
  min: number
  max: number
}

export interface SnapshotTraits {
  revision: number
  unknownNewerRevision: boolean
  minReaderRevision: number
  /** `min_reader_revision` is above what this viewer knows: nothing of the DB is read. */
  needsNewerReader: boolean
  hasExperimentTables: boolean
  hasEvalAnnotations: boolean
  hasSpanAnnotations: boolean
  metricLayout: MetricLayout
  /** Levels stored in `metric_buckets`; null when the DB has none. */
  bucketLevels: BucketLevelRange | null
}

type RevisionTraits = Pick<
  SnapshotTraits,
  'hasExperimentTables' | 'hasEvalAnnotations' | 'hasSpanAnnotations' | 'metricLayout'
>

const REVISION_TRAITS: Record<KnownSchemaRevision, RevisionTraits> = {
  0: {
    hasExperimentTables: true,
    hasEvalAnnotations: false,
    hasSpanAnnotations: false,
    metricLayout: 'dynamic-metrics',
  },
  1: {
    hasExperimentTables: true,
    hasEvalAnnotations: true,
    hasSpanAnnotations: true,
    metricLayout: 'dynamic-metrics',
  },
  2: {
    hasExperimentTables: true,
    hasEvalAnnotations: true,
    hasSpanAnnotations: true,
    metricLayout: 'dynamic-metrics',
  },
  3: {
    hasExperimentTables: true,
    hasEvalAnnotations: true,
    hasSpanAnnotations: true,
    metricLayout: 'metric-points',
  },
}

function firstNumber(database: Database, query: string): number | null {
  const value = database.exec(query)[0]?.values[0]?.[0]
  return typeof value === 'number' ? value : null
}

function recordedRevision(database: Database, tables: Set<string>): number {
  if (tables.has('exp_schema_migrations')) {
    const revision = firstNumber(database, 'SELECT MAX(version) FROM exp_schema_migrations')
    if (revision !== null) return revision
  }
  return firstNumber(database, 'PRAGMA user_version') ?? 0
}

function readSchemaInfo(database: Database, tables: Set<string>): Map<string, number> {
  if (!tables.has('exp_schema_info')) return new Map()
  const rows = database.exec('SELECT key, value FROM exp_schema_info')[0]?.values ?? []
  const info = new Map<string, number>()
  for (const [key, value] of rows) {
    const parsed = Number(value)
    if (typeof key === 'string' && Number.isInteger(parsed)) info.set(key, parsed)
  }
  return info
}

function storedBucketLevels(info: Map<string, number>): BucketLevelRange | null {
  const min = info.get('bucket_min_level')
  const max = info.get('bucket_max_level')
  return min !== undefined && max !== undefined && min <= max ? { min, max } : null
}

const UNREADABLE_TRAITS: RevisionTraits = {
  hasExperimentTables: false,
  hasEvalAnnotations: false,
  hasSpanAnnotations: false,
  metricLayout: 'dynamic-metrics',
}

function closestKnownRevision(revision: number): KnownSchemaRevision {
  const known = KNOWN_SCHEMA_REVISIONS.filter((candidate) => candidate <= revision)
  return known[known.length - 1] ?? KNOWN_SCHEMA_REVISIONS[0]
}

/** Decides what a snapshot DB contains; the only place that reads revisions or probes the schema. */
export function readSnapshotTraits(database: Database): SnapshotTraits {
  const tableRows = database.exec("SELECT name FROM sqlite_master WHERE type = 'table'")
  const tables = new Set((tableRows[0]?.values ?? []).map((row) => String(row[0])))
  const revision = recordedRevision(database, tables)
  const info = readSchemaInfo(database, tables)
  const minReaderRevision = info.get('min_reader_revision') ?? 0
  const needsNewerReader = minReaderRevision > NEWEST_KNOWN_REVISION
  const traits: SnapshotTraits = {
    revision,
    unknownNewerRevision: revision > NEWEST_KNOWN_REVISION,
    minReaderRevision,
    needsNewerReader,
    ...(needsNewerReader ? UNREADABLE_TRAITS : REVISION_TRAITS[closestKnownRevision(revision)]),
    bucketLevels: null,
  }
  if (needsNewerReader) return traits
  // SDKs before 0.1.0 zipped exp.db while its data was still in the WAL file, so a
  // published revision 0 snapshot can be a database without any tables.
  if (revision === 0 && tables.size === 0) traits.hasExperimentTables = false
  // The migration runner baselines a pre-0.1.0 DB at revision 1 without creating the
  // annotation tables, so revisions 1 and 2 do not guarantee that they exist.
  if (!tables.has('eval_annotations')) traits.hasEvalAnnotations = false
  if (!tables.has('span_annotations')) traits.hasSpanAnnotations = false
  if (!tables.has('metric_points') || !tables.has('metric_keys')) {
    traits.metricLayout = 'dynamic-metrics'
  }
  if (traits.metricLayout === 'metric-points' && tables.has('metric_buckets')) {
    traits.bucketLevels = storedBucketLevels(info)
  }
  return traits
}
