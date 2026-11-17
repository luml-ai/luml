import { beforeAll, describe, expect, it } from 'vitest'
import sqlite3InitModule, { type Database, type Sqlite3Static } from '@sqlite.org/sqlite-wasm'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import type { MetricBucket, MetricCatalogEntry } from '@/metric-buckets/types'
import { zipped } from './helpers/metricDatabases'

/*
 * An oracle independent of the code under test and of the test helpers: the databases are
 * written with literal SQL (revision 3 with the SDK's migration and write-path statements),
 * the stored rows are read back with their SQLite types, and every bucket is recomputed in
 * BigInt by brute force. Compared on revision 2 and revision 3 at every level 0-31.
 */

interface StoredValue {
  value: unknown
  type: string
}

interface StoredRow {
  key: StoredValue
  step: StoredValue
  value: StoredValue
}

interface ExpectedBucket extends MetricBucket {
  sumAbs: number
}

interface ExpectedSeries {
  first_step: number | null
  last_step: number | null
  buckets: ExpectedBucket[]
}

const SUMMABLE_LIMIT = 1e290

const bucketable = (rows: StoredRow[]) =>
  rows.filter((row) => row.step.type === 'integer' && row.key.type === 'text')

const isNumeric = (row: StoredRow) => row.value.type === 'real' || row.value.type === 'integer'

const stepOf = (row: StoredRow) => BigInt(row.step.value as number | bigint)

function expectedSeries(
  rows: StoredRow[],
  key: string,
  level: number,
  startStep: number | null,
  endStep: number | null,
): ExpectedSeries {
  const points = bucketable(rows).filter((row) => row.key.value === key)
  if (!points.length) return { first_step: null, last_step: null, buckets: [] }
  const steps = points.map(stepOf)
  const first = steps.reduce((min, step) => (step < min ? step : min))
  const last = steps.reduce((max, step) => (step > max ? step : max))
  const series: ExpectedSeries = { first_step: Number(first), last_step: Number(last), buckets: [] }
  const start = startStep === null ? first : BigInt(startStep)
  const end = endStep === null ? last : BigInt(endStep)
  if (start > end) return series
  const shift = BigInt(2 * level)
  const buckets = new Map<bigint, ExpectedBucket>()
  for (const point of points) {
    const step = stepOf(point)
    const index = step >> shift
    if (index < start >> shift || index > end >> shift) continue
    let bucket = buckets.get(index)
    if (!bucket) {
      bucket = {
        bucket: Number(index),
        first_step: Number(step),
        last_step: Number(step),
        count: 0,
        finite_count: 0,
        min: null,
        max: null,
        sum: null,
        sumAbs: 0,
      }
      buckets.set(index, bucket)
    }
    bucket.count++
    bucket.first_step = Math.min(bucket.first_step, Number(step))
    bucket.last_step = Math.max(bucket.last_step, Number(step))
    if (!isNumeric(point)) continue
    const value = Number(point.value.value)
    bucket.min = bucket.min === null ? value : Math.min(bucket.min, value)
    bucket.max = bucket.max === null ? value : Math.max(bucket.max, value)
    if (value < -SUMMABLE_LIMIT || value > SUMMABLE_LIMIT) continue
    bucket.finite_count++
    bucket.sum = (bucket.sum ?? 0) + value
    bucket.sumAbs += Math.abs(value)
  }
  series.buckets = [...buckets.values()].sort((left, right) => left.bucket - right.bucket)
  return series
}

function expectedCatalog(rows: StoredRow[]): MetricCatalogEntry[] {
  const keys = [...new Set(bucketable(rows).map((row) => row.key.value as string))].sort()
  return keys.map((key) => {
    const points = bucketable(rows).filter((row) => row.key.value === key)
    const values = points.filter(isNumeric).map((row) => Number(row.value.value))
    const steps = points.map((row) => Number(row.step.value))
    return {
      key,
      first_step: steps.reduce((min, step) => Math.min(min, step)),
      last_step: steps.reduce((max, step) => Math.max(max, step)),
      count: points.length,
      min: values.length ? values.reduce((min, value) => Math.min(min, value)) : null,
      max: values.length ? values.reduce((max, value) => Math.max(max, value)) : null,
    }
  })
}

const SUMMABLE = "typeof(value) IN ('real', 'integer') AND value BETWEEN -1e290 AND 1e290"
const VALUE_AGGREGATES =
  `count(*), count(CASE WHEN ${SUMMABLE} THEN 1 END), ` +
  "min(CASE WHEN typeof(value) IN ('real', 'integer') THEN value END), " +
  "max(CASE WHEN typeof(value) IN ('real', 'integer') THEN value END), " +
  `sum(CASE WHEN ${SUMMABLE} THEN value END)`
const BUCKET_COLUMNS =
  'level, metric_id, bucket, count, finite_count, min, max, sum, first_step, last_step'

const REVISION_2_DDL = `
  CREATE TABLE static_params (key TEXT PRIMARY KEY, value TEXT, value_type TEXT);
  CREATE TABLE dynamic_metrics (key TEXT, value REAL, step INTEGER,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (key, step));
  CREATE TABLE exp_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
  INSERT INTO exp_schema_migrations (version) VALUES (1), (2);
  PRAGMA user_version = 2;`

const MIGRATION_003 = `
  CREATE TABLE metric_keys (id INTEGER PRIMARY KEY, key TEXT NOT NULL UNIQUE);
  CREATE TABLE metric_points (metric_id INTEGER NOT NULL, step INTEGER NOT NULL, value REAL,
    logged_ms INTEGER,
    logged_at TIMESTAMP GENERATED ALWAYS AS
      (strftime('%Y-%m-%d %H:%M:%S', logged_ms / 1000, 'unixepoch')) VIRTUAL,
    PRIMARY KEY (metric_id, step)) WITHOUT ROWID;
  CREATE TABLE metric_buckets (level INTEGER NOT NULL, metric_id INTEGER NOT NULL,
    bucket INTEGER NOT NULL, count INTEGER NOT NULL, finite_count INTEGER NOT NULL, min REAL,
    max REAL, sum REAL, first_step INTEGER NOT NULL, last_step INTEGER NOT NULL,
    PRIMARY KEY (level, metric_id, bucket)) WITHOUT ROWID;
  CREATE TABLE exp_schema_info (key TEXT PRIMARY KEY, value TEXT NOT NULL) WITHOUT ROWID;
  INSERT INTO metric_keys (key) SELECT DISTINCT key FROM dynamic_metrics ORDER BY key;
  INSERT INTO metric_points (metric_id, step, value, logged_ms)
    SELECT k.id, d.step, d.value, NULL FROM dynamic_metrics d JOIN metric_keys k ON k.key = d.key
    WHERE typeof(d.step) = 'integer' ORDER BY k.id, d.step;
  DROP TABLE dynamic_metrics;
  INSERT INTO metric_buckets (${BUCKET_COLUMNS})
    SELECT 3, metric_id, step >> 6, ${VALUE_AGGREGATES}, min(step), max(step)
    FROM metric_points GROUP BY metric_id, step >> 6;`

const BUILD_UPPER_LEVEL = `
  INSERT INTO metric_buckets (${BUCKET_COLUMNS})
  SELECT ?, metric_id, bucket >> 2, sum(count), sum(finite_count), min(min), max(max),
         sum(sum), min(first_step), max(last_step)
  FROM metric_buckets WHERE level = ? GROUP BY metric_id, bucket >> 2`

const FINISH_MIGRATION = `
  CREATE VIEW dynamic_metrics AS
    SELECT k.key AS key, p.value AS value, p.step AS step, p.logged_at AS logged_at
    FROM metric_points p JOIN metric_keys k ON k.id = p.metric_id;
  INSERT INTO exp_schema_info VALUES ('min_reader_revision', '2'), ('min_writer_revision', '3'),
    ('bucket_min_level', '3'), ('bucket_max_level', '12');
  INSERT INTO exp_schema_migrations (version) VALUES (3);
  PRAGMA user_version = 3;`

const REBUILD_POINT_LEVEL = `
  INSERT OR REPLACE INTO metric_buckets (${BUCKET_COLUMNS})
  SELECT 3, ?1, ?2, ${VALUE_AGGREGATES}, min(step), max(step)
  FROM metric_points
  WHERE metric_id = ?1 AND step BETWEEN ?2 << 6 AND (?2 << 6) + 63
  HAVING count(*) > 0`

const REBUILD_UPPER_LEVEL = `
  INSERT OR REPLACE INTO metric_buckets (${BUCKET_COLUMNS})
  SELECT ?3, ?1, ?2, sum(count), sum(finite_count), min(min), max(max), sum(sum),
         min(first_step), max(last_step)
  FROM metric_buckets
  WHERE level = ?3 - 1 AND metric_id = ?1 AND bucket BETWEEN ?2 * 4 AND ?2 * 4 + 3
  HAVING count(*) > 0`

/** A point as SQL literals, so text, BLOB, huge and infinite values go in exactly. */
interface LiteralPoint {
  key: string
  step: string
  value: string
}

const text = (value: string) => `'${value.replace(/'/g, "''")}'`

function literalNumber(value: number): string {
  if (value === Infinity) return '9e999'
  if (value === -Infinity) return '-9e999'
  return value.toPrecision(17)
}

const point = (key: string, step: number, value: number | null): LiteralPoint => ({
  key: text(key),
  step: String(step),
  value: value === null ? 'NULL' : literalNumber(value),
})

const WIDTH_12 = 4 ** 12

function cleanPoints(): LiteralPoint[] {
  const points: LiteralPoint[] = []
  for (let step = -150; step < 150; step++) points.push(point('neg', step, Math.sin(step) * 10))
  for (const step of [-1, 0, 63, 64, WIDTH_12 - 1, WIDTH_12, WIDTH_12 + 1, -WIDTH_12]) {
    points.push(point('edge', step, step / 7))
  }
  points.push(point('edge', -WIDTH_12 - 1, 1), point('edge', -(4 ** 15) - 7, 2))
  points.push(point('edge', 4 ** 15 + 3, 3))
  for (const step of [0, 1000, 1e6, 1e9, 3e12, 2 ** 52, -(2 ** 52)]) {
    points.push(point('sparse', step, step % 97))
  }
  const specials = [null, Infinity, -Infinity, 1e300, -1e300, 1e290, -1e290, 1.0000001e290, 5, 0]
  specials.forEach((value, index) => points.push(point('special', index * 50, value)))
  points.push({ key: text('special'), step: '1000', value: "'abc'" })
  points.push({ key: text('special'), step: '1001', value: "x'00ff'" })
  points.push({ key: text('special'), step: '1002', value: "'12.5'" })
  points.push(point('one', 777, 1.25))
  points.push(point('allnull', 5, null), point('allnull', 6, null))
  points.push({ key: text('alltext'), step: '9', value: "'zz'" })
  points.push(point('over', 10, 1), point('over', 11, 2), point('over', 10, 100))
  points.push(point('over', 200, 3))
  for (let step = 0; step < 64; step++) points.push(point('cancel', step, step % 2 ? 1e16 : -1e16))
  points.push(point('cancel', 64, 1))
  return points
}

/** Rows only a released SDK could write; revision 2 keeps them, the reads skip them. */
const LEGACY_ONLY: LiteralPoint[] = [
  { key: text('neg'), step: '2.5', value: '1' },
  { key: text('neg'), step: "'x'", value: '1' },
  { key: text('neg'), step: "x'0100000000000000'", value: '1' },
  { key: text('neg'), step: 'NULL', value: '1' },
  { key: "x'6b6b'", step: '3', value: '1' },
  { key: 'NULL', step: '4', value: '1' },
  { key: '42', step: '5', value: '1' },
  { key: text('realstep'), step: '7.0', value: '1' },
]

/** Written through the revision 3 write path after migrating: overwrite, out of order, new key. */
const LIVE_WRITES: LiteralPoint[] = [
  point('over', 11, -50),
  point('neg', -1000, 7),
  point('neg', 5, 1e300),
  point('newkey', 3, 2),
  point('edge', 64, 1e295),
  point('cancel', 63, 1),
]

const KEYS = [
  'neg',
  'edge',
  'sparse',
  'special',
  'one',
  'allnull',
  'alltext',
  'over',
  'cancel',
  '42',
  'realstep',
  'newkey',
  'missing',
  'neg',
]

const RANGES: [number | null, number | null][] = [
  [null, null],
  [-1, 0],
  [63, 64],
  [1, 62],
  [64 * 5 + 3, 64 * 9 - 7],
  [WIDTH_12 - 1, WIDTH_12],
  [-1e15, 1e15],
  [5, 4],
  [0, 0],
  [-WIDTH_12 - 1, -WIDTH_12 - 1],
  [-16_777_217, -16_777_217],
  [10 ** 12, null],
  [300, null],
  [null, -100],
  [-(2 ** 53) + 1, 2 ** 53 - 1],
]

const READ_REVISION_2 =
  'SELECT key, typeof(key), step, typeof(step), value, typeof(value) FROM dynamic_metrics'
const READ_REVISION_3 = `SELECT k.key, typeof(k.key), p.step, typeof(p.step), p.value, typeof(p.value)
  FROM metric_points p JOIN metric_keys k ON k.id = p.metric_id`

let sqlite: Sqlite3Static

function insertLegacy(db: Database, points: LiteralPoint[]): void {
  for (const { key, step, value } of points) {
    db.exec(
      `INSERT OR REPLACE INTO dynamic_metrics (key, value, step) VALUES (${key}, ${value}, ${step})`,
    )
  }
}

/** The SDK write path: replace the points, then rebuild every touched bucket level by level. */
function writeRevision3(db: Database, points: LiteralPoint[]): void {
  let touched = new Map<string, [number, bigint]>()
  for (const { key, step, value } of points) {
    db.exec(`INSERT OR IGNORE INTO metric_keys (key) VALUES (${key})`)
    const id = Number(db.selectValue(`SELECT id FROM metric_keys WHERE key = ${key}`))
    db.exec(
      `INSERT OR REPLACE INTO metric_points (metric_id, step, value, logged_ms)
       VALUES (${id}, ${step}, ${value}, NULL)`,
    )
    const bucket = BigInt(step) >> 6n
    touched.set(`${id}:${bucket}`, [id, bucket])
  }
  for (const [id, bucket] of touched.values()) {
    db.exec({ sql: REBUILD_POINT_LEVEL, bind: [id, bucket] })
  }
  for (let level = 4; level <= 12; level++) {
    const parents = new Map<string, [number, bigint]>()
    for (const [id, bucket] of touched.values())
      parents.set(`${id}:${bucket >> 2n}`, [id, bucket >> 2n])
    touched = parents
    for (const [id, bucket] of touched.values()) {
      db.exec({ sql: REBUILD_UPPER_LEVEL, bind: [id, bucket, level] })
    }
  }
}

function storedRows(db: Database, sql: string): StoredRow[] {
  const rows: StoredRow[] = []
  db.exec({
    sql,
    rowMode: 'array',
    callback: (row: unknown[]) => {
      const step = typeof row[2] === 'bigint' ? Number(row[2]) : row[2]
      rows.push({
        key: { value: row[0], type: String(row[1]) },
        step: { value: step, type: String(row[3]) },
        value: { value: row[4], type: String(row[5]) },
      })
    },
  })
  return rows
}

function exportDatabase(db: Database): Uint8Array {
  db.exec('VACUUM')
  const bytes = sqlite.capi.sqlite3_js_db_export(db)
  db.close()
  return bytes
}

const stored = new Map<string, StoredRow[]>()
let provider: ExperimentSnapshotDatabaseProvider

beforeAll(async () => {
  sqlite = await sqlite3InitModule()
  const revision2 = new sqlite.oo1.DB(':memory:')
  revision2.exec(REVISION_2_DDL)
  insertLegacy(revision2, [...cleanPoints(), ...LEGACY_ONLY])
  stored.set('rev2', storedRows(revision2, READ_REVISION_2))

  const revision3 = new sqlite.oo1.DB(':memory:')
  revision3.exec('PRAGMA page_size = 16384')
  revision3.exec(REVISION_2_DDL)
  insertLegacy(revision3, cleanPoints())
  revision3.exec(MIGRATION_003)
  for (let level = 4; level <= 12; level++) {
    revision3.exec({ sql: BUILD_UPPER_LEVEL, bind: [level, level - 1] })
  }
  revision3.exec(FINISH_MIGRATION)
  writeRevision3(revision3, LIVE_WRITES)
  stored.set('rev3', storedRows(revision3, READ_REVISION_3))

  provider = new ExperimentSnapshotDatabaseProvider()
  await provider.init({
    modelsInfo: [
      { modelId: 'rev2', buffer: await zipped(exportDatabase(revision2)) },
      {
        modelId: 'rev3',
        source: { kind: 'raw', buffer: exportDatabase(revision3).slice().buffer },
      },
    ],
  })
}, 60_000)

function rowsOf(modelId: string): StoredRow[] {
  const rows = stored.get(modelId)
  if (!rows) throw new Error(`no stored rows for ${modelId}`)
  return rows
}

describe('metric buckets against an independent BigInt oracle', () => {
  it('serves the catalog and skipped-row count the stored rows imply', async () => {
    for (const result of await provider.getMetricCatalogs()) {
      if (!result.ok) throw new Error(JSON.stringify(result))
      const rows = rowsOf(result.modelId)
      const exact = expectedCatalog(rows)
      // Revision 2 reads only the (key, step) index: no count, min or max, and a fractional
      // REAL step is left out without being counted.
      const legacy = result.value.revision < 3
      expect(result.value.metrics, result.modelId).toEqual(
        legacy ? exact.map((entry) => ({ ...entry, count: null, min: null, max: null })) : exact,
      )
      const skipped = rows.filter(
        (row) => row.key.type !== 'text' || ['null', 'text', 'blob'].includes(row.step.type),
      )
      expect(result.value.skipped_rows, result.modelId).toBe(legacy ? skipped.length : 0)
    }
  })

  it('serves every key at every level 0-31 over every range set exactly', async () => {
    const mismatches: string[] = []
    let compared = 0
    for (let level = 0; level <= 31; level++) {
      for (const [start, end] of RANGES) {
        const results = await provider.getMetricBuckets({
          keys: KEYS,
          start_step: start,
          end_step: end,
          level,
        })
        for (const result of results) {
          const label = `${result.modelId} level ${level} [${start}, ${end}]`
          if (!result.ok) {
            mismatches.push(`${label}: ${result.error.code} ${result.error.message}`)
            continue
          }
          expect(result.value.series.map((series) => series.key)).toEqual(KEYS)
          for (const series of result.value.series) {
            compared++
            const expected = expectedSeries(rowsOf(result.modelId), series.key, level, start, end)
            const exact = (bucket: MetricBucket) => ({ ...bucket, sum: bucket.sum === null })
            const actualExact = JSON.stringify([
              series.first_step,
              series.last_step,
              series.buckets.map(exact),
            ])
            const expectedExact = JSON.stringify([
              expected.first_step,
              expected.last_step,
              expected.buckets.map(({ sumAbs: _sumAbs, ...bucket }) => exact(bucket)),
            ])
            if (actualExact !== expectedExact) {
              mismatches.push(`${label} ${series.key}: ${actualExact} vs ${expectedExact}`)
              continue
            }
            series.buckets.forEach((bucket, index) => {
              const reference = expected.buckets[index]
              if (bucket.sum === null || !reference || reference.sum === null) return
              if (Math.abs(bucket.sum - reference.sum) > 1e-9 * reference.sumAbs) {
                mismatches.push(`${label} ${series.key} bucket ${bucket.bucket} sum ${bucket.sum}`)
              }
            })
          }
        }
      }
    }
    expect(compared).toBe(32 * RANGES.length * 2 * KEYS.length)
    expect(mismatches.slice(0, 10)).toEqual([])
  }, 60_000)
})
