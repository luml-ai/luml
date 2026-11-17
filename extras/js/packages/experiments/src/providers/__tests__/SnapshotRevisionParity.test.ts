import { beforeAll, describe, expect, it } from 'vitest'
import { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import type { Trace } from '../ExperimentSnapshotApiProvider.interface'
import type {
  EvalsInfo,
  GetEvalsByDatasetParams,
  GetTracesParams,
  TraceSpan,
  TypedEvalsColumns,
} from '@/interfaces/interfaces'
import {
  DATASET_EVAL_IDS_SQL,
  EVAL_ANNOTATION_FIELDS_SQL,
  summariesAnswerTraceFilters,
  TRACE_ANNOTATIONS_SQL,
} from '../snapshotTraceQueries'
import {
  editedDatabase,
  fixtureDatabase,
  providerDatabase,
  providerTraits,
  queryPlan,
  rawProvider,
  recordSql,
} from './helpers/traceSnapshots'

// Every trace and eval read gives the same result, in the same order, on a revision 2
// snapshot and on a revision 3 snapshot of the same rows. Rows are inserted so that table
// order differs from every index order: ids are shuffled, timestamps and sort values tie,
// eval ids repeat across datasets, and evals and traces have several links.

const MODEL = 'parity'
const SAME_TIME = '2026-01-01 00:00:00'
const LATER = '2026-01-02 00:00:00'

type Json = Record<string, unknown>

// trace, span, parent, start, end, status, attributes, created_at
const SPANS: [string, string, string | null, number, number, number | null, Json | null, string][] =
  [
    ['t2', 's9', null, 0, 50, 1, { k: 1, mixed: 'text' }, LATER],
    ['t2', 's1', 's9', 10, 20, 2, { k: 2.5 }, LATER],
    ['t3', 's5', null, 0, 30, 2, { mixed: 3 }, SAME_TIME],
    ['t3', 's2', 's5', 0, 30, null, null, SAME_TIME],
    ['t1', 's7', null, 5, 35, 1, { k: 'x', mixed: true }, SAME_TIME],
    ['t1', 's3', 's7', 5, 20, 0, { k: 0 }, SAME_TIME],
    ['t1', 's4', 's7', 5, 20, 1, {}, SAME_TIME],
    ['t4', 's8', 'missing', 1, 31, 1, { k: 7 }, SAME_TIME],
    ['t0', 's6', null, 2, 52, 1, { z: 1, k: 3 }, LATER],
    ['t0', 's0', 's6', 2, 12, 1, { z: 'a' }, LATER],
  ]

// id, dataset, inputs, scores, created_at
const EVALS: [string, string, Json, Json | null, string][] = [
  ['e3', 'd2', { q: 3 }, { acc: 0.1, f1: 1, g: 'x', h: 2 }, SAME_TIME],
  ['e1', 'd2', { q: 'one' }, { acc: 0.2, f1: 'n/a', h: 'y' }, LATER],
  ['e6', 'd1', { q: 6, w: 'z' }, { g: 1, acc: 0.3 }, LATER],
  ['e2', 'd1', { q: 2 }, { acc: 0.3, f1: 0.5, g: 1 }, SAME_TIME],
  ['e1', 'd1', { q: 1 }, { acc: 1e16, f1: 2 }, SAME_TIME],
  ['e5', 'd1', { w: 1, q: 'five' }, { f1: 0.5, g: 'two', acc: 0.3, y: 1 }, SAME_TIME],
  ['e3', 'd1', { q: 3 }, { acc: 0.1, x: true }, LATER],
  ['e4', 'd1', { q: 4 }, null, SAME_TIME],
]

// id, dataset, eval, trace
const LINKS: [string, string, string, string][] = [
  ['b1', 'd1', 'e2', 't2'],
  ['b7', 'd1', 'e2', 't1'],
  ['b3', 'd2', 'e3', 't3'],
  ['b5', 'd1', 'e1', 't3'],
  ['b2', 'd1', 'e1', 't1'],
  ['b9', 'd2', 'e1', 't2'],
  ['b4', 'd1', 'e1', 't2'],
  ['b6', 'd1', 'e6', 't0'],
]

// id, dataset, eval, name, kind, value_type, value
const EVAL_ANNOTATIONS: [string, string, string, string, string, string, string][] = [
  ['a2', 'd1', 'e2', 'answer', 'expectation', 'bool', 'true'],
  ['a9', 'd1', 'e1', 'quality', 'feedback', 'bool', 'true'],
  ['a1', 'd1', 'e1', 'quality', 'feedback', 'bool', 'false'],
  ['a5', 'd2', 'e1', 'quality', 'feedback', 'bool', 'true'],
  ['a3', 'd1', 'e1', 'answer', 'expectation', 'string', 'bird'],
  ['a7', 'd1', 'e1', 'answer', 'expectation', 'int', '4'],
  ['a4', 'd1', 'e6', 'tone', 'feedback', 'bool', 'false'],
  ['a8', 'd1', 'e5', 'answer', 'expectation', 'string', 'fish'],
]

// id, trace, span, name, kind, value_type, value
const SPAN_ANNOTATIONS: [string, string, string, string, string, string, string][] = [
  ['n8', 't1', 's3', 'ok', 'feedback', 'bool', 'true'],
  ['n2', 't1', 's3', 'ok', 'feedback', 'bool', 'false'],
  ['n5', 't1', 's7', 'ok', 'feedback', 'int', '3'],
  ['n1', 't3', 's5', 'label', 'expectation', 'string', 'cat'],
  ['n6', 't3', 's2', 'label', 'expectation', 'int', '2'],
  ['n3', 't1', 's3', 'label', 'expectation', 'string', 'dog'],
  ['n4', 't0', 's0', 'ok', 'feedback', 'bool', 'true'],
]

const text = (value: unknown) =>
  value === null || value === undefined ? 'NULL' : `'${String(value).replace(/'/g, "''")}'`
const json = (value: unknown) => (value === null ? 'NULL' : text(JSON.stringify(value)))
const values = (rows: string[][]) => rows.map((row) => `(${row.join(', ')})`).join(',\n')

const INSERT_ROWS = `
  DELETE FROM spans; DELETE FROM evals; DELETE FROM eval_traces_bridge;
  DELETE FROM eval_annotations; DELETE FROM span_annotations;
  INSERT INTO spans (trace_id, span_id, parent_span_id, name, kind, dfs_span_type,
    start_time_unix_nano, end_time_unix_nano, status_code, status_message, attributes, events,
    links, trace_flags, created_at) VALUES ${values(
      SPANS.map(([trace, span, parent, start, end, status, attributes, created]) => [
        text(trace),
        text(span),
        text(parent),
        text(`op-${span}`),
        '1',
        '0',
        String(start),
        String(end),
        status === null ? 'NULL' : String(status),
        status === 2 ? text('boom') : 'NULL',
        json(attributes),
        span === 's1' ? json([{ name: 'event' }]) : 'NULL',
        'NULL',
        '1',
        text(created),
      ]),
    )};
  INSERT INTO evals (id, dataset_id, inputs, outputs, refs, scores, metadata, created_at,
    updated_at) VALUES ${values(
      EVALS.map(([id, dataset, inputs, scores, created]) => [
        text(id),
        text(dataset),
        json(inputs),
        json({ a: id }),
        'NULL',
        json(scores),
        json({ source: dataset }),
        text(created),
        text(created),
      ]),
    )};
  INSERT INTO eval_traces_bridge (id, eval_dataset_id, eval_id, trace_id, created_at)
    VALUES ${values(LINKS.map((link) => [...link.map(text), text(SAME_TIME)]))};
  INSERT INTO eval_annotations (id, dataset_id, eval_id, name, annotation_kind, value_type,
    value, user, created_at) VALUES ${values(
      EVAL_ANNOTATIONS.map((row) => [...row.map(text), text('user'), text(SAME_TIME)]),
    )};
  INSERT INTO span_annotations (id, trace_id, span_id, name, annotation_kind, value_type,
    value, user, created_at) VALUES ${values(
      SPAN_ANNOTATIONS.map((row) => [...row.map(text), text('user'), text(SAME_TIME)]),
    )};
`

const SUMMARY_TABLES = [
  'snapshot_trace_summaries',
  'snapshot_eval_score_stats',
  'snapshot_span_attribute_keys',
  'snapshot_eval_column_keys',
]
const READ_INDEXES = [
  'spans_structure',
  'evals_list',
  'eval_traces_bridge_trace',
  'eval_traces_bridge_eval',
  'span_annotations_span',
  'eval_annotations_eval',
]
const EVAL_JSON_COLUMNS = ['inputs', 'outputs', 'refs', 'scores', 'metadata']
const ROOT_STATUS = 'MAX(CASE WHEN parent_span_id IS NULL THEN status_code END)'
const parsable = (column: string) => `CASE WHEN json_valid(${column}, 2) THEN ${column} END`

// The export's statements (sdk `_snapshot_summaries.py`), run with the read indexes in place
// as the export runs them.
const REBUILD_SUMMARIES = `
  ${SUMMARY_TABLES.map((table) => `DELETE FROM ${table};`).join('\n')}
  INSERT INTO snapshot_trace_summaries
  SELECT trace_id, MIN(start_time_unix_nano), MAX(end_time_unix_nano),
    MAX(end_time_unix_nano) - MIN(start_time_unix_nano), COUNT(*),
    CASE
      WHEN ${ROOT_STATUS} IS NULL THEN 3
      WHEN ${ROOT_STATUS} = 2 THEN 2
      WHEN ${ROOT_STATUS} = 1 THEN 1
      ELSE 0
    END,
    MIN(created_at)
  FROM spans GROUP BY trace_id;
  INSERT INTO snapshot_span_attribute_keys
  SELECT CAST(je.key AS TEXT), je.type
  FROM spans, json_each(${parsable('spans.attributes')}) je
  WHERE spans.attributes IS NOT NULL AND je.key IS NOT NULL
  GROUP BY CAST(je.key AS TEXT);
  INSERT INTO snapshot_eval_score_stats
  SELECT e.dataset_id, CAST(je.key AS TEXT), COUNT(*), TOTAL(je.value)
  FROM evals e,
    json_each(CASE WHEN json_valid(e.scores)
      AND json_type(e.scores) IN ('object', 'array') THEN e.scores END) je
  WHERE e.scores IS NOT NULL AND je.type IN ('integer', 'real', 'true', 'false')
  GROUP BY e.dataset_id, CAST(je.key AS TEXT);
  ${EVAL_JSON_COLUMNS.map(
    (column) => `INSERT INTO snapshot_eval_column_keys
    SELECT dataset_id, '${column}', CAST(je.key AS TEXT), je.type
    FROM evals, json_each(${parsable(`evals.${column}`)}) je
    WHERE evals.${column} IS NOT NULL AND je.key IS NOT NULL
    GROUP BY dataset_id, CAST(je.key AS TEXT);`,
  ).join('\n')}
`

const DROP_SUMMARIES = SUMMARY_TABLES.map((table) => `DROP TABLE ${table};`).join('\n')

const AS_REVISION_2 = `
  ${READ_INDEXES.map((index) => `DROP INDEX ${index};`).join('\n')}
  ${DROP_SUMMARIES}
  DELETE FROM exp_schema_migrations WHERE version >= 3;
  PRAGMA user_version = 2;
`

type Sort = 'created_at' | 'execution_time' | 'span_count'
type Order = 'asc' | 'desc'
type Query = { name: string; search?: string; filters?: string[] }
const TRACE_SORTS: Sort[] = ['created_at', 'execution_time', 'span_count']
const ORDERS: Order[] = ['asc', 'desc']
const DATASETS = ['d1', 'd2']
const EVAL_SORTS = ['created_at', 'id', 'acc', 'f1', 'g']
const VARIANTS = ['with derived tables', 'with indexes only']

const TRACE_QUERIES: Query[] = [
  { name: 'all' },
  { name: 'search', search: 't' },
  { name: 'span count', filters: ['span_count >= 2'] },
  { name: 'state', filters: ['state = "ok"'] },
  { name: 'duration and span count', filters: ['execution_time > 29 AND span_count < 3'] },
  { name: 'created_at', filters: ['created_at >= "2026-01-02"'] },
  { name: 'attribute', filters: ['attributes.k > 0'] },
  { name: 'annotation', filters: ['annotations.ok = "true"'] },
  { name: 'eval', filters: ['evals = "e1"'] },
  { name: 'eval and span count', filters: ['evals != "e2"', 'span_count >= 1'] },
]

const EVAL_QUERIES: Query[] = [
  { name: 'all' },
  { name: 'search', search: 'f' },
  { name: 'score', filters: ['scores.acc >= 0.2'] },
  { name: 'input', filters: ['inputs.q != 9'] },
  { name: 'annotation', filters: ['annotations.answer != "x"'] },
  { name: 'created_at', filters: ['created_at >= "2026-01-01"'] },
]

const traceParams = (sort_by: Sort, order: Order, query: Query) => ({
  sort_by,
  order,
  search: query.search ?? '',
  filters: query.filters ?? [],
})

const evalParams = (
  dataset_id: string,
  sort: string,
  order: Order,
  query: Query = { name: 'all' },
): GetEvalsByDatasetParams => ({
  dataset_id,
  // The UI sorts by score keys too; the provider takes any key.
  sort_by: sort as GetEvalsByDatasetParams['sort_by'],
  order,
  search: query.search ?? '',
  filters: query.filters ?? [],
})

const combos = <T>(sorts: T[]) =>
  sorts.flatMap((sort) => ORDERS.map((order) => [sort, order] as const))

async function allPages<T>(reset: () => Promise<void>, next: () => Promise<T[]>): Promise<T[][]> {
  await reset()
  const pages: T[][] = []
  for (;;) {
    const page = await next()
    if (!page.length) return pages
    pages.push(page)
  }
}

const tracePages = (provider: ExperimentSnapshotDatabaseProvider, params: GetTracesParams) =>
  allPages(
    () => provider.resetTracesRequestParams(),
    () => provider.getTraces(params),
  )

const evalPages = (provider: ExperimentSnapshotDatabaseProvider, params: GetEvalsByDatasetParams) =>
  allPages(
    () => provider.resetEvalsDatasetsRequestParams(),
    () => provider.getNextEvalsByDatasetId(params),
  )

/**
 * Open difference (not fixed, see LM-1100): in a descending list revision 3 walks its index
 * backwards, so rows with the same sort value come in descending id order, while revisions 0
 * to 2 keep them in ascending id order. With ties put in id order on both sides the rows, the
 * sort values and the page sizes are still compared.
 */
function tiesInIdOrder<T>(pages: T[][], value: (row: T) => unknown, id: (row: T) => string) {
  const rows = pages.flat()
  const run = (row: T) => rows.findIndex((other) => value(other) === value(row))
  const sorted = [...rows].sort((a, b) => {
    if (run(a) !== run(b)) return run(a) - run(b)
    return id(a) < id(b) ? -1 : id(a) > id(b) ? 1 : 0
  })
  return { sizes: pages.map((page) => page.length), rows: sorted }
}

const evalCreatedAt = (row: EvalsInfo) =>
  EVALS.find(([id, dataset]) => id === row.id && dataset === row.dataset_id)?.[4]

/** The tree the UI renders: the structure, each span completed by its payload. */
async function fullTree(
  provider: ExperimentSnapshotDatabaseProvider,
  traceId: string,
): Promise<TraceSpan[]> {
  const spans = (await provider.getTraceSpans(MODEL, traceId)) ?? []
  const merged = await Promise.all(
    spans.map(async (span) =>
      span.payloadLoaded
        ? span
        : {
            ...span,
            ...(await provider.getSpanPayload(MODEL, traceId, span.span_id)),
            payloadLoaded: true,
          },
    ),
  )
  return provider.buildSpanTree(merged)
}

function valueTypes(datasetId: string, column: 'inputs' | 'scores'): Map<string, Set<string>> {
  const types = new Map<string, Set<string>>()
  for (const [, dataset, inputs, scores] of EVALS) {
    if (dataset !== datasetId) continue
    for (const [key, value] of Object.entries((column === 'inputs' ? inputs : scores) ?? {})) {
      types.set(key, (types.get(key) ?? new Set()).add(typeof value))
    }
  }
  return types
}

/**
 * Open difference (SDK export, see LM-1100): the key catalog keeps the type of the eval the
 * export reads first, not of the eval with the lowest id that revisions 0 to 2 take it from,
 * so a key whose values have mixed types can get another type.
 */
function mixedTypesHidden(columns: TypedEvalsColumns, datasetId: string) {
  const hide = (column: 'inputs' | 'scores') => {
    const types = valueTypes(datasetId, column)
    return columns[column].map(({ name, type }) => ({
      name,
      type: (types.get(name)?.size ?? 0) > 1 ? 'mixed' : type,
    }))
  }
  return { ...columns, inputs: hide('inputs'), scores: hide('scores') }
}

const TRACE_IDS = [...new Set(SPANS.map(([trace]) => trace))]
const SPAN_KEYS = SPANS.map(([trace, span]) => [trace, span] as const)
const EVAL_KEYS = EVALS.map(([id, dataset]) => [dataset, id] as const)

let revision2Bytes: Uint8Array
const revision3Bytes: Record<string, Uint8Array> = {}

beforeAll(async () => {
  const withRows = await editedDatabase(fixtureDatabase('i_gen2_sdk_0_6_0').bytes, INSERT_ROWS)
  revision2Bytes = await editedDatabase(withRows, AS_REVISION_2)
  revision3Bytes['with derived tables'] = await editedDatabase(withRows, REBUILD_SUMMARIES)
  revision3Bytes['with indexes only'] = await editedDatabase(withRows, DROP_SUMMARIES)
})

describe.each(VARIANTS)(
  'a revision 3 snapshot %s reads like a revision 2 snapshot of the same rows',
  (variant) => {
    let old: ExperimentSnapshotDatabaseProvider
    let current: ExperimentSnapshotDatabaseProvider
    const withDerived = variant === 'with derived tables'

    beforeAll(async () => {
      old = await rawProvider(MODEL, revision2Bytes)
      current = await rawProvider(MODEL, revision3Bytes[variant]!)
    })

    it('reads each snapshot on its own path', () => {
      expect(providerTraits(old)).toMatchObject({
        revision: 2,
        structuralTraces: false,
        hasTraceSummaries: false,
      })
      expect(providerTraits(current)).toMatchObject({
        revision: 3,
        structuralTraces: true,
        hasTraceSummaries: withDerived,
        hasScoreStats: withDerived,
        hasKeyCatalogs: withDerived,
      })
    })

    describe.each(TRACE_QUERIES)('trace list: $name', (query) => {
      it.each(combos(TRACE_SORTS))('by %s %s, whole and page by page', async (sort, order) => {
        const params = traceParams(sort, order, query)
        const paged = { ...params, limit: 2 }
        const read = async (provider: ExperimentSnapshotDatabaseProvider) => [
          [await provider.getAllTraces(params)],
          await tracePages(provider, paged),
          [await provider.getFreshTraces(paged)],
        ]
        const expected = await read(old)
        expect(expected[0]![0]!.length).toBeGreaterThan(0)
        const actual = await read(current)
        if (withDerived && order === 'desc' && summariesAnswerTraceFilters(params.filters)) {
          const normalized = (pages: Trace[][]) =>
            tiesInIdOrder(
              pages,
              (trace) => trace[sort],
              (trace) => trace.trace_id,
            )
          expect(actual.map(normalized)).toEqual(expected.map(normalized))
        } else {
          expect(actual).toEqual(expected)
        }
      })
    })

    it.each(TRACE_IDS)('trace %s: the tree with payloads', async (traceId) => {
      expect(await fullTree(current, traceId)).toEqual(await fullTree(old, traceId))
    })

    it('trace columns, annotation summary and span annotations', async () => {
      expect(await current.getTracesColumns(MODEL)).toEqual(await old.getTracesColumns(MODEL))
      expect(await current.getTracesAnnotationSummary(MODEL)).toEqual(
        await old.getTracesAnnotationSummary(MODEL),
      )
      for (const [traceId, spanId] of SPAN_KEYS) {
        expect(await current.getSpanAnnotations(MODEL, traceId, spanId)).toEqual(
          await old.getSpanAnnotations(MODEL, traceId, spanId),
        )
      }
    })

    describe.each(DATASETS)('dataset %s', (datasetId) => {
      describe.each(EVAL_QUERIES)('evals: $name', (query) => {
        it.each(combos(EVAL_SORTS))('by %s %s, whole and page by page', async (sort, order) => {
          const params = evalParams(datasetId, sort, order, query)
          const paged = { ...params, limit: 2 }
          const read = async (provider: ExperimentSnapshotDatabaseProvider) => [
            [await provider.getAllDatasetEvals(params)],
            await evalPages(provider, paged),
            [await provider.getFreshEvalsByDatasetId(paged)],
          ]
          const expected = await read(old)
          const actual = await read(current)
          if (sort === 'created_at' && order === 'desc') {
            const normalized = (pages: EvalsInfo[][]) =>
              tiesInIdOrder(pages, evalCreatedAt, (row) => row.id)
            expect(actual.map(normalized)).toEqual(expected.map(normalized))
          } else {
            expect(actual).toEqual(expected)
          }
        })

        it('average scores', async () => {
          const filtered = Boolean(query.search || query.filters)
          const [expected] = await old.getDatasetAverageScores(
            datasetId,
            query.search,
            query.filters,
          )
          const [actual] = await current.getDatasetAverageScores(
            datasetId,
            query.search,
            query.filters,
          )
          // Accepted: score stats give the keys sorted by name.
          const scores =
            withDerived && !filtered
              ? [...expected!.scores].sort((a, b) => (a.name < b.name ? -1 : 1))
              : expected!.scores
          expect(actual!.scores).toEqual(scores)
        })
      })

      it('eval columns and the annotation summary', async () => {
        const columns = await current.getEvalsColumns(datasetId)
        const expected = await old.getEvalsColumns(datasetId)
        if (withDerived) {
          expect(mixedTypesHidden(columns, datasetId)).toEqual(
            mixedTypesHidden(expected, datasetId),
          )
        } else {
          expect(columns).toEqual(expected)
        }
        expect(await current.getEvalsDatasetAnnotationsSummary(datasetId)).toEqual(
          await old.getEvalsDatasetAnnotationsSummary(datasetId),
        )
      })

      it('compare-mode rows', async () => {
        for (const cursor of [null, 'e2']) {
          const batch = { dataset_id: datasetId, limit: 2, cursor }
          const expected = await old.getBatchExperimentEvals(batch)
          // Accepted: revision 3 reads only the requested dataset's rows.
          expect(await current.getBatchExperimentEvals(batch)).toEqual({
            ...expected,
            items: expected.items.filter((item) => item.dataset_id === datasetId),
          })
        }
      })
    })

    it('eval rows, annotations and links to traces', async () => {
      for (const [datasetId, evalId] of EVAL_KEYS) {
        expect(await current.getEvalAnnotations(MODEL, datasetId, evalId)).toEqual(
          await old.getEvalAnnotations(MODEL, datasetId, evalId),
        )
        const link = { modelId: MODEL, datasetId, evalId }
        expect(await current.getTraceId(link)).toBe(await old.getTraceId(link))
        expect(await current.getEvalById(MODEL, evalId)).toEqual(
          await old.getEvalById(MODEL, evalId),
        )
      }
      expect(await current.getUniqueDatasetsIds()).toEqual(await old.getUniqueDatasetsIds())
    })
  },
)

describe.each(VARIANTS)('compare mode of two experiments on revision 3 %s', (variant) => {
  async function twoExperiments(bytes: Uint8Array) {
    const provider = new ExperimentSnapshotDatabaseProvider()
    await provider.init({
      modelsInfo: ['a', 'b'].map((modelId) => ({
        modelId,
        source: { kind: 'raw' as const, buffer: bytes.slice().buffer },
      })),
    })
    return provider
  }

  it.each(DATASETS)('pages the evals of dataset %s like revision 2', async (datasetId) => {
    const old = await twoExperiments(revision2Bytes)
    const current = await twoExperiments(revision3Bytes[variant]!)
    const params = { ...evalParams(datasetId, 'created_at', 'desc'), limit: 2 }
    const expected = await evalPages(old, params)
    // Accepted: revision 3 reads only the requested dataset's rows.
    expect(await evalPages(current, params)).toEqual(
      expected.map((page) => page.filter((item) => item.dataset_id === datasetId)),
    )
  })
})

describe('the reads that pin the order on revision 3', () => {
  let old: ExperimentSnapshotDatabaseProvider
  let current: ExperimentSnapshotDatabaseProvider
  const plan = (sql: string, params: string[]) =>
    queryPlan(providerDatabase(current), sql, params).join('\n')

  beforeAll(async () => {
    old = await rawProvider(MODEL, revision2Bytes)
    current = await rawProvider(MODEL, revision3Bytes['with indexes only']!)
  })

  async function readEverything(provider: ExperimentSnapshotDatabaseProvider) {
    for (const traceId of TRACE_IDS) await provider.getTraceSpans(MODEL, traceId)
    await provider.getAllTraces(traceParams('span_count', 'desc', { name: 'all' }))
    await provider.getTracesColumns(MODEL)
    for (const datasetId of DATASETS) {
      await provider.getAllDatasetEvals(evalParams(datasetId, 'acc', 'desc'))
      await provider.getDatasetAverageScores(datasetId, undefined, ['scores.acc >= 0.2'])
      await provider.getEvalsColumns(datasetId)
      await provider.getEvalsDatasetAnnotationsSummary(datasetId)
    }
  }

  it('leave the SQL of revisions 0 to 2 as it was', async () => {
    const statements = recordSql(old)
    await readEverything(old)
    expect(statements.length).toBeGreaterThan(0)
    for (const pinned of ['rowid', '+id', 'MIN(evals.id)', ', id\n']) {
      expect(statements.filter((sql) => sql.includes(pinned))).toEqual([])
    }
  })

  it('read through the indexes, the averages without reading eval rows', async () => {
    const statements = recordSql(current)
    await readEverything(current)
    const averages = statements.find((sql) => sql.startsWith('SELECT scores FROM evals'))!
    expect(averages).toContain('ORDER BY +id')
    expect(plan(averages, ['d1', '$.acc', '0.2'])).toContain('COVERING INDEX evals_list')
    expect(plan(TRACE_ANNOTATIONS_SQL, ['t1'])).toContain('INDEX span_annotations_span')
    expect(plan(EVAL_ANNOTATION_FIELDS_SQL, ['feedback', 'd1'])).toContain(
      'INDEX eval_annotations_eval',
    )
    const ids = plan(DATASET_EVAL_IDS_SQL, ['d1'])
    expect(ids).toContain('COVERING INDEX sqlite_autoindex_evals_1')
    expect(ids).not.toContain('TEMP B-TREE')
  })
})
