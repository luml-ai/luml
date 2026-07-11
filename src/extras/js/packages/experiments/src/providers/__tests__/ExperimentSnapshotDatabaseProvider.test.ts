import { describe, it, expect, beforeAll } from 'vitest'
import { createRequire } from 'node:module'
import initSqlJs, { type Database, type SqlJsStatic } from 'sql.js'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import type { ModelSnapshot } from '@/interfaces/interfaces'

const require = createRequire(import.meta.url)

let SQL: SqlJsStatic

beforeAll(async () => {
  SQL = await initSqlJs({ locateFile: () => require.resolve('sql.js/dist/sql-wasm.wasm') })
})

function databaseWithMetrics(rows: Array<{ key: string; value: number; step: number }>): Database {
  const db = new SQL.Database()
  db.run('CREATE TABLE dynamic_metrics (key TEXT, value REAL, step INTEGER)')
  const stmt = db.prepare('INSERT INTO dynamic_metrics (key, value, step) VALUES (?, ?, ?)')
  for (const row of rows) {
    stmt.run([row.key, row.value, row.step])
  }
  stmt.free()
  return db
}

function providerFor(db: Database): ExperimentSnapshotDatabaseProvider {
  const provider = new ExperimentSnapshotDatabaseProvider()
  ;(provider as unknown as { _modelsSnapshots: ModelSnapshot[] })._modelsSnapshots = [
    { modelId: 'm1', database: db },
  ]
  return provider
}

describe('ExperimentSnapshotDatabaseProvider.getModelDynamicMetricData', () => {
  it('returns points in ascending step order when rows are stored out of order', async () => {
    const db = databaseWithMetrics([
      { key: 'loss', value: 30, step: 3 },
      { key: 'loss', value: 10, step: 1 },
      { key: 'loss', value: 20, step: 2 },
    ])
    const provider = providerFor(db)

    const [metric] = await provider.getDynamicMetricData('loss')

    expect(metric.x).toEqual([1, 2, 3])
    expect(metric.y).toEqual([10, 20, 30])
  })

  it('filters by metric key while keeping ascending step order', async () => {
    const db = databaseWithMetrics([
      { key: 'acc', value: 1, step: 5 },
      { key: 'loss', value: 30, step: 3 },
      { key: 'acc', value: 2, step: 4 },
      { key: 'loss', value: 10, step: 1 },
    ])
    const provider = providerFor(db)

    const [metric] = await provider.getDynamicMetricData('loss')

    expect(metric.x).toEqual([1, 3])
    expect(metric.y).toEqual([10, 30])
  })
})
