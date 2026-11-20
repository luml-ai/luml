import sqlite3InitModule, { type Database, type Sqlite3Static } from '@sqlite.org/sqlite-wasm'
import JSZip from 'jszip'
import type { MetricBucket, MetricCatalogEntry } from '../../../metric-buckets/types'

export interface MetricPoint {
  key: string
  step: number
  /**
   * Text and BLOB values, which released SDKs could store, count in `count` only. A string
   * must not look like a number: the REAL column's affinity would store it as one.
   */
  value: number | string | Uint8Array | null
}

export interface OracleBucket extends MetricBucket {
  /** Sum of the absolute summable values: the contract's tolerance scale for `sum`. */
  sumAbs: number
}

export const BUCKET_MIN_LEVEL = 3
export const BUCKET_MAX_LEVEL = 12

let sqlite3: Promise<Sqlite3Static> | null = null

function loadSqlite(): Promise<Sqlite3Static> {
  sqlite3 ??= sqlite3InitModule()
  return sqlite3
}

/** Seeded PRNG (mulberry32) so generated experiments are identical on every run. */
export function seededRandom(seed: number): () => number {
  let state = seed >>> 0
  return () => {
    state = (state + 0x6d2b79f5) >>> 0
    let t = state
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

/** The points as stored after `INSERT OR REPLACE` of `points` in order: last write wins. */
export function storedPoints(points: MetricPoint[]): MetricPoint[] {
  const byStep = new Map<string, MetricPoint>()
  for (const point of points) byStep.set(`${point.key}\u0000${point.step}`, point)
  return [...byStep.values()]
}

const SUMMABLE_LIMIT = 1e290

const isSummable = (value: number | null): value is number =>
  value !== null && Math.abs(value) <= SUMMABLE_LIMIT

function emptyBucket(bucket: number, step: number): OracleBucket {
  return {
    bucket,
    first_step: step,
    last_step: step,
    count: 0,
    finite_count: 0,
    min: null,
    max: null,
    sum: null,
    sumAbs: 0,
  }
}

function addPoint(bucket: OracleBucket, { step, value }: MetricPoint): void {
  bucket.count++
  bucket.first_step = Math.min(bucket.first_step, step)
  bucket.last_step = Math.max(bucket.last_step, step)
  if (typeof value !== 'number') return
  bucket.min = bucket.min === null ? value : Math.min(bucket.min, value)
  bucket.max = bucket.max === null ? value : Math.max(bucket.max, value)
  if (!isSummable(value)) return
  bucket.finite_count++
  bucket.sum = (bucket.sum ?? 0) + value
  bucket.sumAbs += Math.abs(value)
}

/**
 * Brute-force reference: every bucket of `key` at `level` that has points and intersects
 * `[startStep, endStep]`, whole. Deliberately simple; it is the oracle for all sources.
 */
export function oracleBuckets(
  points: MetricPoint[],
  key: string,
  level: number,
  startStep: number | null = null,
  endStep: number | null = null,
): OracleBucket[] {
  return bucketsOfStored(storedPoints(points), key, level, startStep, endStep)
}

function bucketsOfStored(
  stored: MetricPoint[],
  key: string,
  level: number,
  startStep: number | null,
  endStep: number | null,
): OracleBucket[] {
  const keyPoints = stored.filter((point) => point.key === key)
  if (!keyPoints.length) return []
  // An open side is the key's own first or last step, so a start past the data is empty.
  const start = startStep ?? keyPoints.reduce((min, point) => Math.min(min, point.step), Infinity)
  const end = endStep ?? keyPoints.reduce((max, point) => Math.max(max, point.step), -Infinity)
  if (start > end) return []
  const width = 4 ** level
  const firstBucket = Math.floor(start / width)
  const lastBucket = Math.floor(end / width)
  const buckets = new Map<number, OracleBucket>()
  for (const point of keyPoints) {
    const index = Math.floor(point.step / width)
    if (index < firstBucket || index > lastBucket) continue
    let bucket = buckets.get(index)
    if (!bucket) buckets.set(index, (bucket = emptyBucket(index, point.step)))
    addPoint(bucket, point)
  }
  return [...buckets.values()].sort((left, right) => left.bucket - right.bucket)
}

export function oracleCatalog(points: MetricPoint[]): MetricCatalogEntry[] {
  const keys = [...new Set(storedPoints(points).map((point) => point.key))].sort()
  return keys.map((key) => {
    const all = oracleBuckets(points, key, 0)
    // At level 0 every bucket is one point, so a bucket's min is that point's value.
    const values = all.flatMap((bucket) => (bucket.min === null ? [] : [bucket.min]))
    return {
      key,
      first_step: all[0]?.first_step ?? 0,
      last_step: all.at(-1)?.last_step ?? 0,
      count: all.length,
      min: values.length ? values.reduce((min, value) => Math.min(min, value)) : null,
      max: values.length ? values.reduce((max, value) => Math.max(max, value)) : null,
    }
  })
}

/** A revision 0-2 catalog reads only the (key, step) index: no count, min or max. */
export function legacyCatalog(entries: MetricCatalogEntry[]): MetricCatalogEntry[] {
  return entries.map((entry) => ({ ...entry, count: null, min: null, max: null }))
}

/**
 * sqlite-wasm binds every integral JS number as int64, which wraps beyond 2^63; such values
 * are bound as text instead, which the REAL columns convert back exactly.
 */
function realBinding(value: MetricPoint['value']): MetricPoint['value'] {
  return typeof value === 'number' && Number.isInteger(value) && !Number.isSafeInteger(value)
    ? String(value)
    : value
}

function exportDatabase(loaded: Sqlite3Static, db: Database): Uint8Array {
  db.exec('VACUUM')
  const bytes = loaded.capi.sqlite3_js_db_export(db)
  db.close()
  return bytes
}

const REVISION_2_DDL = `
  CREATE TABLE static_params (key TEXT PRIMARY KEY, value TEXT, value_type TEXT);
  CREATE TABLE dynamic_metrics (
    key TEXT, value REAL, step INTEGER, logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    PRIMARY KEY (key, step)
  );
  CREATE TABLE exp_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
  INSERT INTO exp_schema_migrations (version) VALUES (1), (2);
  PRAGMA user_version = 2;
`

/** A revision 2 experiment DB holding `points`, written in order like the SDK writes them. */
export async function revision2Database(points: MetricPoint[], extraSql = ''): Promise<Uint8Array> {
  const loaded = await loadSqlite()
  const db = new loaded.oo1.DB(':memory:')
  db.exec(REVISION_2_DDL + extraSql)
  db.transaction(() => {
    const insert = db.prepare(
      'INSERT OR REPLACE INTO dynamic_metrics (key, value, step) VALUES (?, ?, ?)',
    )
    for (const { key, value, step } of points) {
      insert.bind([key, realBinding(value), step]).stepReset()
    }
    insert.finalize()
  })
  return exportDatabase(loaded, db)
}

// Section 2 of the LM-1100 contract, verbatim.
const REVISION_3_DDL = `
  CREATE TABLE static_params (key TEXT PRIMARY KEY, value TEXT, value_type TEXT);
  CREATE TABLE metric_keys (
    id INTEGER PRIMARY KEY,
    key TEXT NOT NULL UNIQUE
  );
  CREATE TABLE metric_points (
    metric_id INTEGER NOT NULL,
    step INTEGER NOT NULL,
    value REAL,
    logged_ms INTEGER,
    logged_at TIMESTAMP GENERATED ALWAYS AS
      (strftime('%Y-%m-%d %H:%M:%S', logged_ms / 1000, 'unixepoch')) VIRTUAL,
    PRIMARY KEY (metric_id, step)
  ) WITHOUT ROWID;
  CREATE TABLE metric_buckets (
    level INTEGER NOT NULL,
    metric_id INTEGER NOT NULL,
    bucket INTEGER NOT NULL,
    count INTEGER NOT NULL,
    finite_count INTEGER NOT NULL,
    min REAL,
    max REAL,
    sum REAL,
    first_step INTEGER NOT NULL,
    last_step INTEGER NOT NULL,
    PRIMARY KEY (level, metric_id, bucket)
  ) WITHOUT ROWID;
  CREATE TABLE exp_schema_info (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
  ) WITHOUT ROWID;
  CREATE VIEW dynamic_metrics AS
  SELECT k.key AS key, p.value AS value, p.step AS step, p.logged_at AS logged_at
  FROM metric_points p JOIN metric_keys k ON k.id = p.metric_id;
  CREATE TRIGGER dynamic_metrics_no_legacy_insert INSTEAD OF INSERT ON dynamic_metrics
  BEGIN
    SELECT RAISE(ABORT, 'this experiment uses schema revision 3; upgrade luml-sdk to write to it');
  END;
  CREATE TABLE exp_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
`

export interface Revision3Options {
  /** Recorded revision; above 3 simulates a newer SDK. */
  revision?: number
  minReaderRevision?: number
  /** Stored bucket levels recorded in `exp_schema_info`; 3 to 12 by default. */
  bucketLevels?: { min: number; max: number }
}

/** Aggregates one level per pass in JS; the DB's own SQL is never trusted to build buckets. */
function insertOracleBuckets(
  db: Database,
  points: MetricPoint[],
  ids: Map<string, number>,
  levels: { min: number; max: number },
): void {
  const insert = db.prepare(
    `INSERT INTO metric_buckets
       (level, metric_id, bucket, count, finite_count, min, max, sum, first_step, last_step)
     VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)`,
  )
  const byKey = new Map<string, MetricPoint[]>()
  for (const point of storedPoints(points)) {
    const keyPoints = byKey.get(point.key)
    if (keyPoints) keyPoints.push(point)
    else byKey.set(point.key, [point])
  }
  for (const [key, keyPoints] of byKey) {
    for (let level = levels.min; level <= levels.max; level++) {
      for (const bucket of bucketsOfStored(keyPoints, key, level, null, null)) {
        insert
          .bind([
            level,
            ids.get(key) ?? null,
            bucket.bucket,
            bucket.count,
            bucket.finite_count,
            realBinding(bucket.min),
            realBinding(bucket.max),
            realBinding(bucket.sum),
            bucket.first_step,
            bucket.last_step,
          ])
          .stepReset()
      }
    }
  }
  insert.finalize()
}

/** A revision 3 experiment DB built from the contract's DDL, with 16 KiB pages like an export. */
export async function revision3Database(
  points: MetricPoint[],
  options: Revision3Options = {},
): Promise<Uint8Array> {
  const loaded = await loadSqlite()
  const db = new loaded.oo1.DB(':memory:')
  const revision = options.revision ?? 3
  const levels = options.bucketLevels ?? { min: BUCKET_MIN_LEVEL, max: BUCKET_MAX_LEVEL }
  db.exec('PRAGMA page_size = 16384')
  db.exec(REVISION_3_DDL)
  db.exec({
    sql:
      'INSERT INTO exp_schema_migrations (version) VALUES ' +
      Array.from({ length: revision }, (_, index) => `(${index + 1})`).join(', '),
  })
  db.exec(`PRAGMA user_version = ${revision}`)
  const info: [string, number][] = [
    ['min_reader_revision', options.minReaderRevision ?? 2],
    ['min_writer_revision', 3],
    ['bucket_min_level', levels.min],
    ['bucket_max_level', levels.max],
  ]
  db.transaction(() => {
    for (const [key, value] of info) {
      db.exec({
        sql: 'INSERT INTO exp_schema_info (key, value) VALUES (?, ?)',
        bind: [key, String(value)],
      })
    }
    const keys = [...new Set(points.map((point) => point.key))].sort()
    const ids = new Map(keys.map((key, index) => [key, index + 1]))
    for (const [key, id] of ids) {
      db.exec({ sql: 'INSERT INTO metric_keys (id, key) VALUES (?, ?)', bind: [id, key] })
    }
    const insert = db.prepare(
      'INSERT OR REPLACE INTO metric_points (metric_id, step, value, logged_ms) VALUES (?, ?, ?, ?)',
    )
    for (const { key, step, value } of points) {
      insert
        .bind([ids.get(key) ?? null, step, realBinding(value), 1_700_000_000_000 + step])
        .stepReset()
    }
    insert.finalize()
    insertOracleBuckets(db, points, ids, levels)
  })
  return exportDatabase(loaded, db)
}

export async function zipped(db: Uint8Array): Promise<ArrayBuffer> {
  const zip = new JSZip()
  zip.file('exp.db', db)
  return zip.generateAsync({ type: 'arraybuffer' })
}

/** A copy whose buffer holds exactly the DB, as the provider's raw source expects. */
export function rawBuffer(db: Uint8Array): ArrayBuffer {
  return db.slice().buffer
}
