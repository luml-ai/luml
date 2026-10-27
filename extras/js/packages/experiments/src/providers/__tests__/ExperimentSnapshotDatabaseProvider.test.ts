import { describe, it, expect, beforeAll, beforeEach, afterEach } from 'vitest'
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

describe('ExperimentSnapshotDatabaseProvider eval annotations', () => {
  let db: Database
  let provider: ExperimentSnapshotDatabaseProvider

  beforeEach(() => {
    db = new SQL.Database()
    db.run(`
      PRAGMA user_version = 1;
      CREATE TABLE evals (
        id TEXT, dataset_id TEXT, inputs TEXT, outputs TEXT, refs TEXT, scores TEXT, metadata TEXT
      );
      CREATE TABLE eval_annotations (
        id TEXT, eval_id TEXT, dataset_id TEXT, name TEXT, annotation_kind TEXT,
        value TEXT, user TEXT, value_type TEXT, created_at TEXT, rationale TEXT
      );
      INSERT INTO evals (id, dataset_id) VALUES ('e1', 'ds1'), ('e2', 'ds1'), ('e3', 'ds2');
    `)
    const stmt = db.prepare(`
      INSERT INTO eval_annotations
        (id, eval_id, dataset_id, name, annotation_kind, value, user, value_type, created_at, rationale)
      VALUES (?, ?, ?, ?, ?, ?, 'annotator', ?, '2026-10-07T00:00:00Z', NULL)
    `)
    for (const row of [
      ['f1', 'e1', 'ds1', 'helpful', 'feedback', 'false', 'bool'],
      ['f2', 'e2', 'ds1', 'helpful', 'feedback', 'false', 'bool'],
      ['f3', 'e2', 'ds1', 'helpful', 'feedback', 'true', 'bool'],
      ['b1', 'e1', 'ds1', 'label', 'expectation', 'false', 'bool'],
      ['b2', 'e2', 'ds1', 'label', 'expectation', 'true', 'bool'],
      ['i1', 'e1', 'ds1', 'rating', 'expectation', '-12', 'int'],
      ['i2', 'e1', 'ds1', 'zero', 'expectation', '0', 'int'],
      ['s1', 'e1', 'ds1', 'text', 'expectation', 'false', 'string'],
      ['s2', 'e1', 'ds1', 'empty', 'expectation', '', 'string'],
      ['other', 'e3', 'ds2', 'helpful', 'feedback', 'true', 'bool'],
    ]) {
      stmt.run(row)
    }
    stmt.free()
    provider = providerFor(db)
  })

  afterEach(() => {
    db.close()
  })

  it('returns typed annotation values and preserves their metadata', async () => {
    const annotations = await provider.getEvalAnnotations('m1', 'ds1', 'e1')

    expect(annotations).toEqual(
      [
        {
          id: 'f1',
          name: 'helpful',
          annotation_kind: 'feedback',
          value_type: 'bool',
          value: false,
        },
        {
          id: 'b1',
          name: 'label',
          annotation_kind: 'expectation',
          value_type: 'bool',
          value: false,
        },
        { id: 'i1', name: 'rating', annotation_kind: 'expectation', value_type: 'int', value: -12 },
        { id: 'i2', name: 'zero', annotation_kind: 'expectation', value_type: 'int', value: 0 },
        {
          id: 's1',
          name: 'text',
          annotation_kind: 'expectation',
          value_type: 'string',
          value: 'false',
        },
        {
          id: 's2',
          name: 'empty',
          annotation_kind: 'expectation',
          value_type: 'string',
          value: '',
        },
      ].map((annotation) => ({
        ...annotation,
        user: 'annotator',
        created_at: '2026-10-07T00:00:00Z',
        rationale: null,
      })),
    )
    expect(await provider.getEvalAnnotations('m1', 'ds1', 'e2')).toMatchObject([
      { id: 'f2', value: false },
      { id: 'f3', value: true },
      { id: 'b2', value: true },
    ])
  })

  it('counts typed boolean values and retains integer and string expectations in dataset summaries', async () => {
    expect(await provider.getEvalsDatasetAnnotationsSummary('ds1')).toEqual({
      feedback: [{ name: 'helpful', total: 3, counts: { false: 2, true: 1 } }],
      expectations: [
        { name: 'label', total: 2, positive: 1, negative: 1, value: null },
        { name: 'rating', total: 1, positive: 0, negative: 0, value: -12 },
        { name: 'zero', total: 1, positive: 0, negative: 0, value: 0 },
        { name: 'text', total: 1, positive: 0, negative: 0, value: 'false' },
        { name: 'empty', total: 1, positive: 0, negative: 0, value: '' },
      ],
    })
  })

  it('includes typed summaries for only the requested eval', async () => {
    const evaluation = await provider.getEvalById('m1', 'e1')

    expect(evaluation.id).toBe('e1')
    expect(evaluation.annotations).toEqual({
      feedback: [{ name: 'helpful', total: 1, counts: { false: 1 } }],
      expectations: [
        { name: 'label', total: 1, positive: 0, negative: 1, value: null },
        { name: 'rating', total: 1, positive: 0, negative: 0, value: -12 },
        { name: 'zero', total: 1, positive: 0, negative: 0, value: 0 },
        { name: 'text', total: 1, positive: 0, negative: 0, value: 'false' },
        { name: 'empty', total: 1, positive: 0, negative: 0, value: '' },
      ],
    })
  })

  it('returns empty annotations and summaries when no annotations match', async () => {
    expect(await provider.getEvalAnnotations('m1', 'ds1', 'missing')).toEqual([])
    expect(await provider.getEvalsDatasetAnnotationsSummary('missing')).toEqual({
      feedback: [],
      expectations: [],
    })
  })

  it('supports snapshots without annotation tables', async () => {
    db.run('PRAGMA user_version = 0; DROP TABLE eval_annotations;')

    expect(await provider.getEvalAnnotations('m1', 'ds1', 'e1')).toEqual([])
    expect(await provider.getEvalsDatasetAnnotationsSummary('ds1')).toEqual({
      feedback: [],
      expectations: [],
    })
    expect((await provider.getEvalById('m1', 'e1')).annotations).toEqual({
      feedback: [],
      expectations: [],
    })
  })
})
