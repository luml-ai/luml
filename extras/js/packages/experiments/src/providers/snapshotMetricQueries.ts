import type { SnapshotDatabase as Database, SqlValue } from './snapshot-source/SnapshotDatabase'
import type { SnapshotTraits } from './ExperimentSnapshotTraits'
import type {
  ExperimentMetricCatalog,
  MetricBucket,
  MetricBucketSeries,
  MetricBucketsRequest,
  MetricBucketsResponse,
  MetricCatalogEntry,
} from '../metric-buckets/types'
import {
  assertBucketLevel,
  bucketOf,
  bucketStepRange,
  MAX_RETURNED_BUCKETS,
} from '../metric-buckets/levels'
import { TooManyBucketsError } from '../metric-buckets/errors'

const numeric = (value: string) => `typeof(${value}) IN ('real', 'integer')`
/** Values `finite_count` and `sum` cover; the limit keeps any sum of them from overflowing. */
const summable = (value: string) => `${numeric(value)} AND ${value} BETWEEN -1e290 AND 1e290`

/**
 * Released SDKs stored numpy integers as BLOB steps, floats as REAL steps and sometimes
 * non-text keys; such rows cannot be bucketed and are left out on revisions 0-2.
 */
const LEGACY_VALID_ROW = "typeof(step) = 'integer' AND typeof(key) = 'text'"

/** count, finite_count, min, max, sum over raw points, as section 4 of the contract defines them. */
const rawAggregates = (value: string) =>
  `count(*), count(CASE WHEN ${summable(value)} THEN 1 END), ` +
  `min(CASE WHEN ${numeric(value)} THEN ${value} END), ` +
  `max(CASE WHEN ${numeric(value)} THEN ${value} END), ` +
  `sum(CASE WHEN ${summable(value)} THEN ${value} END)`

type BucketSource =
  | { kind: 'bucket-table' }
  | { kind: 'coarse-aggregate'; topLevel: number }
  | { kind: 'raw-group-by' }

function rows(database: Database, sql: string, params: SqlValue[]): SqlValue[][] {
  const statement = database.prepare(sql)
  try {
    statement.bind(params)
    const result: SqlValue[][] = []
    while (statement.step()) result.push(statement.get())
    return result
  } finally {
    statement.free()
  }
}

function numberOrNull(value: SqlValue | undefined): number | null {
  return typeof value === 'number' ? value : null
}

function catalogEntry(row: SqlValue[]): MetricCatalogEntry {
  return {
    key: String(row[0]),
    first_step: Number(row[1]),
    last_step: Number(row[2]),
    count: Number(row[3]),
    min: numberOrNull(row[4]),
    max: numberOrNull(row[5]),
  }
}

/**
 * Released revisions all have the PRIMARY KEY (key, step) autoindex. Seeks on it need BINARY
 * order on both columns; a partial index may lack rows. Same statement as the SDK.
 */
const LEGACY_KEY_STEP_INDEX = `
SELECT il.name FROM pragma_index_list('dynamic_metrics') il
WHERE il.partial = 0
  AND EXISTS (SELECT 1 FROM pragma_index_xinfo(il.name) x
              WHERE x.seqno = 0 AND x.name = 'key' AND x.coll = 'BINARY')
  AND EXISTS (SELECT 1 FROM pragma_index_xinfo(il.name) x
              WHERE x.seqno = 1 AND x.name = 'step' AND x.coll = 'BINARY')
ORDER BY il."unique" DESC, il.name LIMIT 1`

/**
 * Catalog rows (key, first_step, last_step, skipped) and the non-text key count, by index
 * seeks only. SQLite orders NULL < numbers < text < BLOB, so `key >= '' AND key < x''` holds
 * the text keys, `step < ''` the numeric steps and `step >= ''` the text and BLOB steps.
 */
function legacySeekQueries(index: string): {
  catalog: string
  nonTextKeys: string
  unlistedRealSteps: string
} {
  const table = `dynamic_metrics INDEXED BY "${index.replace(/"/g, '""')}"`
  const integerSteps =
    `SELECT step FROM ${table} WHERE key = k.key AND step < '' ` +
    "AND typeof(step) = 'integer' ORDER BY step"
  return {
    catalog: `
      WITH RECURSIVE k(key) AS (
        SELECT (SELECT key FROM ${table} WHERE key >= '' AND key < x'' ORDER BY key LIMIT 1)
        UNION ALL
        SELECT (SELECT key FROM ${table} WHERE key > k.key AND key < x'' ORDER BY key LIMIT 1)
        FROM k WHERE k.key IS NOT NULL
      )
      SELECT key, (${integerSteps} LIMIT 1), (${integerSteps} DESC LIMIT 1),
             (SELECT count(*) FROM ${table} WHERE key = k.key AND step IS NULL)
             + (SELECT count(*) FROM ${table} WHERE key = k.key AND step >= '')
      FROM k WHERE key IS NOT NULL`,
    nonTextKeys: `
      SELECT (SELECT count(*) FROM ${table} WHERE key IS NULL)
             + (SELECT count(*) FROM ${table} WHERE key < '')
             + (SELECT count(*) FROM ${table} WHERE key >= x'')`,
    // Only asked for a key the first-step seek already walked to its end.
    unlistedRealSteps: `SELECT count(*) FROM ${table} WHERE key = ? AND step < ''`,
  }
}

interface CatalogRead {
  metrics: MetricCatalogEntry[]
  skippedRows: number
}

/**
 * Revisions 0-2: count, min and max are null, as only the index is read. Fractional REAL
 * steps of a listed key are left out of the steps but not counted as skipped; finding them
 * needs a full scan.
 */
function readLegacyCatalog(database: Database): CatalogRead {
  const [indexRow] = rows(database, LEGACY_KEY_STEP_INDEX, [])
  if (!indexRow) return readLegacyScanCatalog(database)
  const { catalog, nonTextKeys, unlistedRealSteps } = legacySeekQueries(String(indexRow[0]))
  let skippedRows = Number(rows(database, nonTextKeys, [])[0]?.[0] ?? 0)
  const metrics: MetricCatalogEntry[] = []
  for (const [key, firstStep, lastStep, skipped] of rows(database, catalog, [])) {
    skippedRows += Number(skipped)
    if (firstStep === null || firstStep === undefined) {
      skippedRows += Number(rows(database, unlistedRealSteps, [key ?? null])[0]?.[0] ?? 0)
      continue
    }
    metrics.push({
      key: String(key),
      first_step: Number(firstStep),
      last_step: Number(lastStep),
      count: null,
      min: null,
      max: null,
    })
  }
  return { metrics, skippedRows }
}

function readLegacyScanCatalog(database: Database): CatalogRead {
  const metrics = rows(
    database,
    `SELECT key, min(step), max(step), count(*),
            min(CASE WHEN ${numeric('value')} THEN value END),
            max(CASE WHEN ${numeric('value')} THEN value END)
     FROM dynamic_metrics
     WHERE ${LEGACY_VALID_ROW}
     GROUP BY key ORDER BY key`,
    [],
  ).map(catalogEntry)
  const [row] = rows(
    database,
    `SELECT count(*) FROM dynamic_metrics WHERE NOT (${LEGACY_VALID_ROW})`,
    [],
  )
  return { metrics, skippedRows: Number(row?.[0] ?? 0) }
}

function catalogSql(traits: SnapshotTraits): { sql: string; params: SqlValue[] } {
  if (traits.bucketLevels) {
    // The top stored level holds a few rows per metric and is contiguous in the level-first
    // key, so this reads a handful of pages however large the experiment is.
    return {
      sql: `SELECT k.key, min(b.first_step), max(b.last_step), sum(b.count), min(b.min), max(b.max)
            FROM metric_buckets b JOIN metric_keys k ON k.id = b.metric_id
            WHERE b.level = ?
            GROUP BY b.metric_id ORDER BY k.key`,
      params: [traits.bucketLevels.max],
    }
  }
  return {
    sql: `SELECT k.key, min(p.step), max(p.step), count(*),
                 min(CASE WHEN ${numeric('p.value')} THEN p.value END),
                 max(CASE WHEN ${numeric('p.value')} THEN p.value END)
          FROM metric_points p JOIN metric_keys k ON k.id = p.metric_id
          GROUP BY p.metric_id ORDER BY k.key`,
    params: [],
  }
}

function readCatalogRows(database: Database, traits: SnapshotTraits): CatalogRead {
  if (!traits.hasExperimentTables) return { metrics: [], skippedRows: 0 }
  if (traits.metricLayout === 'dynamic-metrics') return readLegacyCatalog(database)
  const { sql, params } = catalogSql(traits)
  return { metrics: rows(database, sql, params).map(catalogEntry), skippedRows: 0 }
}

export function readMetricCatalog(
  database: Database,
  traits: SnapshotTraits,
): ExperimentMetricCatalog {
  const { metrics, skippedRows } = readCatalogRows(database, traits)
  return {
    revision: traits.revision,
    bucket_min_level: traits.bucketLevels?.min ?? null,
    bucket_max_level: traits.bucketLevels?.max ?? null,
    skipped_rows: skippedRows,
    metrics,
  }
}

/** Keys that have points, without touching the points on revision 3. */
export function readMetricKeys(database: Database, traits: SnapshotTraits): string[] {
  if (!traits.hasExperimentTables) return []
  const sql =
    traits.metricLayout === 'metric-points'
      ? `SELECT key FROM metric_keys k
         WHERE EXISTS (SELECT 1 FROM metric_points p WHERE p.metric_id = k.id)`
      : 'SELECT DISTINCT key FROM dynamic_metrics'
  // Unconverted, as the viewer always returned them: a legacy table may hold a NULL key.
  return rows(database, sql, []).map((row) => row[0] as string)
}

function bucketSource(traits: SnapshotTraits, level: number): BucketSource {
  const stored = traits.metricLayout === 'metric-points' ? traits.bucketLevels : null
  if (!stored || level < stored.min) return { kind: 'raw-group-by' }
  if (level <= stored.max) return { kind: 'bucket-table' }
  return { kind: 'coarse-aggregate', topLevel: stored.max }
}

const placeholders = (count: number) => Array(count).fill('?').join(', ')

const SELECTED_KEY_IDS = (count: number) =>
  `(SELECT id FROM metric_keys WHERE key IN (${placeholders(count)}))`

/**
 * Rows one key may read before its answer certainly exceeds the bucket cap: a bucket holds at
 * most `childrenPerBucket` rows (distinct steps, or child buckets), so that many times
 * cap + 1 rows span more than cap buckets. -1 is SQLite's "no limit".
 */
function cappedRows(childrenPerBucket: number): number {
  const rows = (MAX_RETURNED_BUCKETS + 1) * childrenPerBucket
  return rows > Number.MAX_SAFE_INTEGER ? -1 : rows
}

/**
 * One `UNION ALL` branch per key, each an index-ordered scan stopped by `LIMIT`, so the
 * outer `GROUP BY` (which must sort) never reads more than the cap allows. Columns:
 * `position` (the key's index), `key`, then the branch's own columns.
 */
function perKeyScans(
  keys: string[],
  scan: (key: string) => { sql: string; params: SqlValue[] },
): { sql: string; params: SqlValue[] } {
  const params: SqlValue[] = []
  const branches = keys.map((key, position) => {
    const branch = scan(key)
    params.push(key, ...branch.params)
    return `SELECT ${position} AS position, ? AS key, * FROM (${branch.sql})`
  })
  return { sql: branches.join(' UNION ALL '), params }
}

interface BucketQuery {
  sql: string
  params: SqlValue[]
  /** Revisions 0-2, when each key's scan stops at a row limit that fractional steps share. */
  legacyFallback: LegacyFallback | null
}

interface LegacyFallback {
  rowLimit: number
  /** The key's scan over integer steps only, as before fractional steps were counted. */
  integerOnly: (key: string) => BucketQuery
}

/**
 * One statement for all keys. Columns: key, bucket, first_step, last_step, count,
 * finite_count, min, max, sum; ordered by key, then bucket. On revisions 0-2 each key may
 * start with a row whose bucket is null: its count is the key's fractional REAL steps within
 * `countSteps`, which the walk reads anyway.
 */
function bucketQuery(
  traits: SnapshotTraits,
  keys: string[],
  level: number,
  firstBucket: number,
  lastBucket: number,
  countSteps: [number, number],
): BucketQuery {
  const [lowStep, highStep] = bucketStepRange(firstBucket, lastBucket, level)
  const source = bucketSource(traits, level)
  if (source.kind === 'bucket-table') {
    // Rows arrive in primary-key order without a sort, so the cap check stops the scan.
    return {
      sql: `SELECT k.key, b.bucket, b.first_step, b.last_step, b.count, b.finite_count,
                   b.min, b.max, b.sum
            FROM metric_buckets b JOIN metric_keys k ON k.id = b.metric_id
            WHERE b.level = ? AND b.metric_id IN ${SELECTED_KEY_IDS(keys.length)}
              AND b.bucket BETWEEN ? AND ?
            ORDER BY b.metric_id, b.bucket`,
      params: [level, ...keys, firstBucket, lastBucket],
      legacyFallback: null,
    }
  }
  if (source.kind === 'coarse-aggregate') {
    const top = source.topLevel
    const children = perKeyScans(keys, (key) => ({
      sql: `SELECT bucket, first_step, last_step, count, finite_count, min, max, sum
            FROM metric_buckets
            WHERE level = ? AND metric_id = (SELECT id FROM metric_keys WHERE key = ?)
              AND bucket BETWEEN ? AND ?
            ORDER BY bucket LIMIT ?`,
      params: [
        top,
        key,
        bucketOf(lowStep, top),
        bucketOf(highStep, top),
        cappedRows(4 ** (level - top)),
      ],
    }))
    return {
      sql: `SELECT key, bucket >> ? AS parent, min(first_step), max(last_step), sum(count),
                   sum(finite_count), min(min), max(max), sum(sum)
            FROM (${children.sql})
            GROUP BY position, parent ORDER BY position, parent`,
      params: [2 * (level - top), ...children.params],
      legacyFallback: null,
    }
  }
  const pointLimit = cappedRows(4 ** level)
  if (traits.metricLayout === 'metric-points') {
    return {
      ...rawGroupBy(keys, level, 'step >> ?', (key) => ({
        sql: `SELECT step, value FROM metric_points
              WHERE metric_id = (SELECT id FROM metric_keys WHERE key = ?)
                AND step BETWEEN ? AND ?
              ORDER BY step LIMIT ?`,
        params: [key, lowStep, highStep, pointLimit],
      })),
      legacyFallback: null,
    }
  }
  const integerOnly = (key: string): BucketQuery => ({
    ...rawGroupBy([key], level, 'step >> ?', (scanKey) => ({
      sql: `SELECT step, value FROM dynamic_metrics
            WHERE key = ? AND step BETWEEN ? AND ? AND ${LEGACY_VALID_ROW}
            ORDER BY step LIMIT ?`,
      params: [scanKey, lowStep, highStep, pointLimit],
    })),
    legacyFallback: null,
  })
  const [countLow, countHigh] = countSteps
  const withFractional = rawGroupBy(
    keys,
    level,
    "CASE WHEN typeof(step) = 'integer' THEN step >> ? END",
    (key) => ({
      sql: `SELECT step, value FROM dynamic_metrics
            WHERE key = ? AND typeof(key) = 'text' AND step BETWEEN ? AND ?
              AND (typeof(step) = 'integer' AND step BETWEEN ? AND ?
                   OR typeof(step) = 'real' AND step BETWEEN ? AND ?)
            ORDER BY step LIMIT ?`,
      params: [
        key,
        Math.min(lowStep, countLow),
        Math.max(highStep, countHigh),
        lowStep,
        highStep,
        countLow,
        countHigh,
        pointLimit,
      ],
    }),
  )
  return {
    ...withFractional,
    legacyFallback: pointLimit === -1 ? null : { rowLimit: pointLimit, integerOnly },
  }
}

/** Each key's scanned points grouped by `bucket`, an expression whose one `?` is the shift. */
function rawGroupBy(
  keys: string[],
  level: number,
  bucket: string,
  scan: (key: string) => { sql: string; params: SqlValue[] },
): { sql: string; params: SqlValue[] } {
  const points = perKeyScans(keys, scan)
  return {
    sql: `SELECT key, ${bucket} AS b, min(step), max(step), ${rawAggregates('value')}
          FROM (${points.sql})
          GROUP BY position, b ORDER BY position, b`,
    params: [2 * level, ...points.params],
  }
}

function bucketFromRow(row: SqlValue[]): MetricBucket {
  return {
    bucket: Number(row[1]),
    first_step: Number(row[2]),
    last_step: Number(row[3]),
    count: Number(row[4]),
    finite_count: Number(row[5]),
    min: numberOrNull(row[6]),
    max: numberOrNull(row[7]),
    sum: numberOrNull(row[8]),
  }
}

interface KeyBuckets {
  buckets: MetricBucket[]
  skippedRows: number
}

/** Reads rows key by key and stops as soon as one key exceeds the bucket cap. */
function collectBuckets(
  database: Database,
  { sql, params, legacyFallback }: BucketQuery,
  modelId: string,
): Map<string, KeyBuckets> {
  const byKey = new Map<string, KeyBuckets>()
  const statement = database.prepare(sql)
  try {
    statement.bind(params)
    while (statement.step()) {
      const row = statement.get()
      const key = String(row[0])
      let read = byKey.get(key)
      if (!read) byKey.set(key, (read = { buckets: [], skippedRows: 0 }))
      if (row[1] === null) {
        read.skippedRows = Number(row[4])
        continue
      }
      if (read.buckets.length === MAX_RETURNED_BUCKETS) {
        throw new TooManyBucketsError(modelId, key, MAX_RETURNED_BUCKETS)
      }
      read.buckets.push(bucketFromRow(row))
    }
  } finally {
    statement.free()
  }
  if (legacyFallback !== null) {
    for (const [key, read] of byKey) {
      const rowsRead = read.buckets.reduce((sum, bucket) => sum + bucket.count, read.skippedRows)
      if (read.skippedRows === 0 || rowsRead < legacyFallback.rowLimit) continue
      // Fractional steps filled part of the cut-short scan, so the integer buckets beyond it
      // are unknown: the integer-only scan reads them (and refuses too many), as the Python
      // reader does. The fractional count stays what was read, a lower bound.
      const integer = collectBuckets(database, legacyFallback.integerOnly(key), modelId)
      read.buckets = integer.get(key)?.buckets ?? []
    }
  }
  return byKey
}

/**
 * The request's inclusive range over integer steps: a fractional bound is rounded inward and
 * an open side stays null (the metric's own first or last step, as in the Python reader).
 */
function requestedSteps(request: MetricBucketsRequest): [number | null, number | null] {
  const start = request.start_step ?? null
  const end = request.end_step ?? null
  if (Number.isNaN(start) || Number.isNaN(end)) throw new RangeError('step bounds must not be NaN')
  return [start === null ? null : Math.ceil(start), end === null ? null : Math.floor(end)]
}

const clampStep = (step: number) =>
  Math.min(Math.max(step, -Number.MAX_SAFE_INTEGER), Number.MAX_SAFE_INTEGER)

const MAX_KEYS_PER_QUERY = 500

/**
 * Steps below -(2^53 - 1) are left out, as the raw-point reads leave them out. Only a key's
 * lowest stored bucket can hold such a step next to safe ones (reads start at the bucket of
 * -(2^53 - 1)); it is aggregated again from the points at safe steps, or dropped.
 */
function dropUnsafeLowSteps(database: Database, byKey: Map<string, KeyBuckets>): void {
  for (const [key, read] of byKey) {
    const lowest = read.buckets[0]
    if (!lowest || lowest.first_step >= -Number.MAX_SAFE_INTEGER) continue
    const [row] = rows(
      database,
      `SELECT ?, ?, min(step), max(step), ${rawAggregates('value')}
       FROM metric_points
       WHERE metric_id = (SELECT id FROM metric_keys WHERE key = ?) AND step BETWEEN ? AND ?`,
      [key, lowest.bucket, key, -Number.MAX_SAFE_INTEGER, lowest.last_step],
    )
    const safe = row ? bucketFromRow(row) : null
    read.buckets = safe?.count ? [safe, ...read.buckets.slice(1)] : read.buckets.slice(1)
  }
}

export function readMetricBuckets(
  database: Database,
  traits: SnapshotTraits,
  modelId: string,
  catalog: ExperimentMetricCatalog,
  request: MetricBucketsRequest,
): MetricBucketsResponse {
  assertBucketLevel(request.level)
  const level = request.level
  const [start, end] = requestedSteps(request)
  const entries = new Map(catalog.metrics.map((entry) => [entry.key, entry]))
  // Compared before clamping. An open side does not widen what is read: every bucket with
  // points of a key lies inside the key's own range.
  const keys = [...new Set(request.keys)].filter((key) => {
    const entry = entries.get(key)
    return entry !== undefined && (start ?? entry.first_step) <= (end ?? entry.last_step)
  })
  const byKey = new Map<string, KeyBuckets>()
  if (keys.length && traits.hasExperimentTables) {
    // Fractional steps are counted within the bounds as given; an open side also counts
    // those beyond the key's integer steps.
    const countSteps: [number, number] = [
      request.start_step ?? -Infinity,
      request.end_step ?? Infinity,
    ]
    const firstBucket = bucketOf(clampStep(start ?? -Infinity), level)
    const lastBucket = bucketOf(clampStep(end ?? Infinity), level)
    // SQLite allows at most 500 terms in a compound SELECT, one per key here.
    for (let from = 0; from < keys.length; from += MAX_KEYS_PER_QUERY) {
      const group = keys.slice(from, from + MAX_KEYS_PER_QUERY)
      const query = bucketQuery(traits, group, level, firstBucket, lastBucket, countSteps)
      for (const [key, read] of collectBuckets(database, query, modelId)) byKey.set(key, read)
    }
    if (bucketSource(traits, level).kind !== 'raw-group-by') {
      dropUnsafeLowSteps(database, byKey)
    }
  }
  const series: MetricBucketSeries[] = request.keys.map((key) => {
    const entry = entries.get(key)
    const read = byKey.get(key)
    return {
      key,
      first_step: entry?.first_step ?? null,
      last_step: entry?.last_step ?? null,
      buckets: read?.buckets ?? [],
      skipped_rows: read?.skippedRows ?? 0,
    }
  })
  return { level, series }
}
