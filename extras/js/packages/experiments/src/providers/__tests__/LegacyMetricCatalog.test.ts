import { beforeAll, describe, expect, it } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import sqlite3InitModule, { type Sqlite3Static } from '@sqlite.org/sqlite-wasm'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import type { ExperimentMetricCatalog, MetricCatalogEntry } from '@/metric-buckets/types'
import { rawBuffer, revision2Database, zipped, type MetricPoint } from './helpers/metricDatabases'
import { FIXTURES_DIR, memoryTransport } from './helpers/snapshotSources'

/*
 * The vectors the SDK tests read too (test_metric_legacy_catalog.py), so both readers return
 * the same catalog for the same revision 0-2 file.
 */
type VectorValue = string | number | null | { blob: string }
type VectorRow = [VectorValue, VectorValue, VectorValue]

interface Vectors {
  cases: {
    name: string
    rows: VectorRow[]
    metrics: [string, number, number][]
    skipped_rows: number
  }[]
  no_index: {
    rows: VectorRow[]
    metrics: [string, number, number, number, number | null, number | null][]
    skipped_rows: number
  }
}

const VECTORS = JSON.parse(
  readFileSync(resolve(FIXTURES_DIR, 'legacy_catalog_vectors.json'), 'utf-8'),
) as Vectors

const DYNAMIC_METRICS = `
  CREATE TABLE dynamic_metrics (key TEXT, value REAL, step INTEGER,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, PRIMARY KEY (key, step));`

const REVISIONS: Record<string, string> = {
  // Released SDKs before the migration runner, with their extra indexes.
  'revision 0': `${DYNAMIC_METRICS}
    CREATE INDEX idx_dynamic_metrics_key ON dynamic_metrics (key);
    CREATE INDEX idx_dynamic_metrics_step ON dynamic_metrics (step);
    CREATE INDEX idx_dynamic_metrics_key_step ON dynamic_metrics (key, step);
    CREATE INDEX idx_dynamic_metrics_logged_at ON dynamic_metrics (logged_at);
    CREATE INDEX idx_dynamic_metrics_key_logged_at ON dynamic_metrics (key, logged_at);`,
  'revision 2': `${DYNAMIC_METRICS}
    CREATE TABLE exp_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
    INSERT INTO exp_schema_migrations (version) VALUES (1), (2);
    PRAGMA user_version = 2;`,
}

const NO_INDEX = `
  CREATE TABLE dynamic_metrics (key TEXT, value REAL, step INTEGER,
    logged_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP);
  CREATE INDEX idx_dynamic_metrics_key ON dynamic_metrics (key);
  CREATE TABLE exp_schema_migrations (version INTEGER PRIMARY KEY, applied_at TEXT);
  INSERT INTO exp_schema_migrations (version) VALUES (1), (2);
  PRAGMA user_version = 2;`

let sqlite: Sqlite3Static

beforeAll(async () => {
  sqlite = await sqlite3InitModule()
})

function decode(value: VectorValue): string | number | null | Uint8Array {
  if (value === null || typeof value !== 'object') return value
  return Uint8Array.from(value.blob.match(/../g) ?? [], (byte) => parseInt(byte, 16))
}

function database(ddl: string, rows: VectorRow[]): Uint8Array {
  const db = new sqlite.oo1.DB(':memory:')
  db.exec(ddl)
  for (const row of rows) {
    db.exec({
      sql: 'INSERT INTO dynamic_metrics (key, value, step) VALUES (?, ?, ?)',
      bind: row.map(decode),
    })
  }
  db.exec('VACUUM')
  const bytes = sqlite.capi.sqlite3_js_db_export(db)
  db.close()
  return bytes
}

async function catalogOf(db: Uint8Array, zip: boolean): Promise<ExperimentMetricCatalog> {
  const provider = new ExperimentSnapshotDatabaseProvider()
  await provider.init({
    modelsInfo: [
      zip
        ? { modelId: 'legacy', buffer: await zipped(db) }
        : { modelId: 'legacy', source: { kind: 'raw', buffer: rawBuffer(db) } },
    ],
  })
  const [result] = await provider.getMetricCatalogs()
  if (!result?.ok) throw new Error(JSON.stringify(result))
  return result.value
}

const transports = [
  ['zip', true],
  ['raw', false],
] as const

describe.each(Object.keys(REVISIONS))('legacy metric catalog on %s', (revision) => {
  describe.each(transports)('read from a %s source', (_, zip) => {
    it.each(VECTORS.cases.map((vector) => [vector.name, vector] as const))(
      'reads keys and steps from the index for %s',
      async (_name, vector) => {
        const catalog = await catalogOf(database(REVISIONS[revision]!, vector.rows), zip)
        expect(catalog.metrics).toEqual(
          vector.metrics.map(
            ([key, first_step, last_step]): MetricCatalogEntry => ({
              key,
              first_step,
              last_step,
              count: null,
              min: null,
              max: null,
            }),
          ),
        )
        expect(catalog.skipped_rows).toBe(vector.skipped_rows)
      },
    )
  })
})

// A partial index may lack rows, so it is not used for the catalog.
const PARTIAL_INDEX = `${NO_INDEX}
  CREATE INDEX idx_partial_key_step ON dynamic_metrics (key, step) WHERE step >= 0;`

describe('legacy metric catalog without a full (key, step) index', () => {
  it.each([
    ['no such index', NO_INDEX],
    ['only a partial one', PARTIAL_INDEX],
  ])('falls back to the exact scan with %s', async (_name, ddl) => {
    const vector = VECTORS.no_index
    const catalog = await catalogOf(database(ddl, vector.rows), true)
    expect(catalog.metrics).toEqual(
      vector.metrics.map(([key, first_step, last_step, count, min, max]) => ({
        key,
        first_step,
        last_step,
        count,
        min,
        max,
      })),
    )
    expect(catalog.skipped_rows).toBe(vector.skipped_rows)
  })
})

describe('legacy metric catalog read by range', () => {
  it('counts the steps of a key without an integer one, never reading a long key', async () => {
    const long: MetricPoint[] = Array.from({ length: 60_000 }, (_, step) => ({
      key: 'long',
      step,
      value: step,
    }))
    const db = await revision2Database(
      long,
      `INSERT INTO dynamic_metrics (key, value, step)
       SELECT 'long', 1.0, step + 0.5 FROM dynamic_metrics WHERE key = 'long';
       INSERT INTO dynamic_metrics (key, value, step) VALUES ('frac', 1.0, 0.25), ('frac', 1.0, 0.75);`,
    )
    const url = 'https://bucket.test/exp.db'
    const { transport, requests } = memoryTransport({ [url]: db })
    const provider = new ExperimentSnapshotDatabaseProvider({ transport })
    await provider.init({
      modelsInfo: [
        { modelId: 'legacy', source: { kind: 'range', url, offset: 0, size: db.length } },
      ],
    })
    const opened = requests.length
    const [result] = await provider.getMetricCatalogs()
    if (!result?.ok) throw new Error(JSON.stringify(result))
    expect(result.value.metrics.map((entry) => entry.key)).toEqual(['long'])
    expect(result.value.skipped_rows).toBe(2)
    const bytes = requests.slice(opened).reduce((sum, request) => sum + request.length, 0)
    expect(bytes, `${bytes} of ${db.length}`).toBeLessThan(db.length / 10)
  })
})
