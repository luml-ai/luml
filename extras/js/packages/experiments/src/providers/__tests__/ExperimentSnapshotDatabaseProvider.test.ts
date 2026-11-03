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

describe('ExperimentSnapshotDatabaseProvider query safety and trace filters', () => {
  let db: Database
  let provider: ExperimentSnapshotDatabaseProvider
  const quoted = "Bob's set"
  const injected = "nope' OR id = 'e2' --"
  const traceParams = {
    limit: 10,
    sort_by: 'created_at' as const,
    order: 'desc' as const,
    search: '',
    filters: [],
  }

  beforeEach(() => {
    db = new SQL.Database()
    db.run(`
      PRAGMA user_version = 1;
      CREATE TABLE evals (
        id TEXT, dataset_id TEXT, inputs TEXT, outputs TEXT, refs TEXT, scores TEXT,
        metadata TEXT, created_at TEXT
      );
      CREATE TABLE eval_traces_bridge (eval_id TEXT, eval_dataset_id TEXT, trace_id TEXT);
      CREATE TABLE spans (
        trace_id TEXT, span_id TEXT, parent_span_id TEXT, name TEXT, kind INTEGER,
        start_time_unix_nano INTEGER, end_time_unix_nano INTEGER, status_code INTEGER,
        status_message TEXT, attributes TEXT, events TEXT, links TEXT, dfs_span_type INTEGER,
        created_at TEXT
      );
      CREATE TABLE eval_annotations (
        id TEXT, eval_id TEXT, dataset_id TEXT, name TEXT, annotation_kind TEXT,
        value TEXT, user TEXT, value_type TEXT, created_at TEXT, rationale TEXT
      );
      CREATE TABLE span_annotations (
        id TEXT, trace_id TEXT, span_id TEXT, name TEXT, annotation_kind TEXT,
        value TEXT, user TEXT, value_type TEXT, created_at TEXT, rationale TEXT
      );
      CREATE TABLE dynamic_metrics (key TEXT, value REAL, step INTEGER);
      CREATE TABLE static_params (key TEXT, value TEXT, value_type TEXT);
    `)
    for (const [index, id] of [quoted, injected, 'e2'].entries()) {
      db.run('INSERT INTO evals VALUES (?, ?, ?, ?, ?, ?, ?, ?)', [
        id,
        id,
        '{"prompt":"hello"}',
        '{}',
        '{}',
        JSON.stringify({ [quoted]: 3 - index }),
        '{}',
        '2026-10-07',
      ])
      db.run('INSERT INTO eval_traces_bridge VALUES (?, ?, ?)', [id, id, id])
      db.run('INSERT INTO spans VALUES (?, ?, NULL, ?, 0, 0, ?, 1, NULL, ?, NULL, NULL, 0, ?)', [
        id,
        id,
        id,
        index === 0 ? 30 : 0,
        '{"label":"hello"}',
        '2026-10-07',
      ])
      db.run('INSERT INTO eval_annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)', [
        id,
        id,
        id,
        'helpful',
        'feedback',
        'True',
        'annotator',
        'bool',
        '2026-10-07',
      ])
      db.run('INSERT INTO span_annotations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)', [
        id,
        id,
        id,
        'helpful',
        'feedback',
        'True',
        'annotator',
        'bool',
        '2026-10-07',
      ])
      db.run('INSERT INTO dynamic_metrics VALUES (?, ?, ?)', [id, index, 1])
    }
    db.run(
      'INSERT INTO spans (trace_id, span_id, start_time_unix_nano, end_time_unix_nano) VALUES (?, ?, 10, 20)',
      [quoted, 'child'],
    )
    provider = providerFor(db)
  })

  afterEach(() => db.close())

  it.each([quoted, injected])('treats lookup values as data: %s', async (id) => {
    expect((await provider.getEvalById('m1', id)).id).toBe(id)
    expect(await provider.getTraceId({ modelId: 'm1', datasetId: id, evalId: id })).toBe(id)
    expect(await provider.getEvalAnnotations('m1', id, id)).toMatchObject([{ id }])
    expect(await provider.getEvalAnnotations('m1', id, 'missing')).toEqual([])
    expect(await provider.getSpanAnnotations('m1', id, id)).toMatchObject([{ id }])
    expect(await provider.getSpanAnnotations('m1', id, 'missing')).toEqual([])
    expect(await provider.getEvalsColumns(id)).toMatchObject({
      inputs: [{ name: 'prompt', type: 'string' }],
      annotations_feedback: [{ name: 'helpful', type: 'boolean' }],
    })
    expect(await provider.getEvalsDatasetAnnotationsSummary(id)).toMatchObject({
      feedback: [{ name: 'helpful', total: 1 }],
    })
    expect((await provider.getDynamicMetricData(id))[0].y).toEqual([id === quoted ? 0 : 1])
    const spans = await provider.getTraceSpans('m1', id)
    expect(spans?.find((span) => span.span_id === id)?.annotation_count).toBe(1)
    const traces = await provider.getFreshTraces({ ...traceParams, search: id })
    expect(traces).toMatchObject([
      { trace_id: id, evals: [id], annotations: { feedback: [{ total: 1 }] } },
    ])
  })

  it('does not return unrelated rows for an injected lookup', async () => {
    await expect(provider.getEvalById('m1', "missing' OR id = 'e2' --")).rejects.toThrow(
      'Eval not found',
    )
    expect(
      await provider.getTraceId({ modelId: 'm1', datasetId: "missing' OR 1=1 --", evalId: 'e2' }),
    ).toBeNull()
    expect(await provider.getEvalAnnotations('m1', "missing' OR 1=1 --", 'e2')).toEqual([])
    expect(await provider.getSpanAnnotations('m1', "missing' OR 1=1 --", 'e2')).toEqual([])
    expect((await provider.getEvalsColumns("missing' OR 1=1 --")).inputs).toEqual([])
    expect((await provider.getDynamicMetricData("missing' OR 1=1 --"))[0].y).toEqual([])
  })

  it.each([
    'span_count > 1',
    '(span_count > 1 OR execution_time > 0)',
    '((span_count > 1 OR execution_time > 0) AND state = "ok")',
    '(span_count > 1 AND attributes.label = "hello")',
    '(execution_time > 100 OR (span_count > 1 AND evals = "Bob\'s set"))',
  ])('applies aggregate filters after grouping: %s', async (filter) => {
    const traces = await provider.getFreshTraces({ ...traceParams, filters: [filter] })
    expect(traces.map((trace) => trace.trace_id)).toEqual([quoted])
    expect(traces[0].span_count).toBe(2)
  })

  it('retains nonaggregate filters and pagination', async () => {
    const params = { ...traceParams, limit: 1, filters: ['attributes.label = "hello"'] }
    expect(await provider.getTraces(params)).toHaveLength(1)
    expect(await provider.getTraces(params)).toHaveLength(1)
    expect(
      await provider.getAllTraces({
        sort_by: 'created_at',
        order: 'desc',
        search: '',
        filters: params.filters,
      }),
    ).toHaveLength(3)
    const evalParams = { ...traceParams, dataset_id: quoted, limit: 1 }
    expect((await provider.getNextEvalsByDatasetId(evalParams)).map((item) => item.id)).toEqual([
      quoted,
    ])
    expect(await provider.getNextEvalsByDatasetId(evalParams)).toEqual([])
  })

  it.each([quoted, injected])('binds JSON filter field names as data: %s', async (key) => {
    db.run('UPDATE evals SET scores = ? WHERE id = ?', [JSON.stringify({ [key]: 5 }), key])
    db.run('UPDATE spans SET attributes = ? WHERE trace_id = ?', [
      JSON.stringify({ [key]: 'match' }),
      key,
    ])
    const evalParams = { ...traceParams, dataset_id: '', filters: [`scores.\`${key}\` = 5`] }
    expect((await provider.getAllDatasetEvals(evalParams)).map((item) => item.id)).toEqual([key])
    expect((await provider.getDatasetAverageScores(key, '', evalParams.filters))[0].scores).toEqual(
      [{ name: key, value: 5 }],
    )
    for (const comparison of ['= "match"', 'ILIKE "MATCH"', 'IN ("match")', 'NOT IN ("other")']) {
      const traces = await provider.getFreshTraces({
        ...traceParams,
        filters: [`attributes.\`${key}\` ${comparison}`],
      })
      expect(traces.map((trace) => trace.trace_id)).toEqual([key])
    }
  })

  it('sorts by score names containing apostrophes without executing SQL', async () => {
    const params = { ...traceParams, sort_by: quoted, dataset_id: '' }
    const evaluations = await provider.getAllDatasetEvals(
      params as Parameters<typeof provider.getAllDatasetEvals>[0],
    )
    expect(evaluations.map((item) => item.id)).toEqual([quoted, injected, 'e2'])
  })

  it('rejects unsafe trace sort columns and binds pagination values', async () => {
    await expect(
      provider.getFreshTraces({
        ...traceParams,
        sort_by: 'created_at; DROP TABLE spans; --',
      } as unknown as typeof traceParams),
    ).rejects.toThrow()
    await expect(
      provider.getFreshTraces({
        ...traceParams,
        limit: '1; DROP TABLE spans; --',
      } as unknown as typeof traceParams),
    ).rejects.toThrow()
    expect(await provider.getAllTraces(traceParams)).toHaveLength(3)
  })

  it('parses SDK boolean values case-insensitively while preserving other types', async () => {
    for (const [key, value, type] of [
      ['upper', 'True', 'bool'],
      ['lower', 'true', 'bool'],
      ['mixed', 'tRuE', 'bool'],
      ['false', 'False', 'bool'],
      ['false_upper', 'FALSE', 'bool'],
      ['text', 'True', 'string'],
      ['rate', '0.1', 'float'],
    ])
      db.run('INSERT INTO static_params VALUES (?, ?, ?)', [key, value, type])
    expect(await provider.getStaticParamsList()).toEqual([
      {
        modelId: 'm1',
        upper: true,
        lower: true,
        mixed: true,
        false: false,
        false_upper: false,
        text: 'True',
        rate: 0.1,
      },
    ])
  })
})
