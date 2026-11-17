import { createHash } from 'node:crypto'
import { beforeAll, describe, expect, it } from 'vitest'
import type { ExperimentSnapshotDatabaseProvider } from '../ExperimentSnapshotDatabaseProvider'
import type { Trace } from '../ExperimentSnapshotApiProvider.interface'
import type { ScoreInfo, TraceSpan, TypedColumnInfo } from '@/interfaces/interfaces'
import {
  EVAL_TRACE_SQL,
  SPAN_ANNOTATION_COUNTS_SQL,
  STRUCTURAL_SPANS_SQL,
  TRACE_EVALS_SQL,
  traceSummariesQuery,
  type TraceSortColumn,
} from '../snapshotTraceQueries'
import {
  editedDatabase,
  fixtureDatabase,
  fixtureProvider,
  providerDatabase,
  providerTraits,
  queryPlan,
  rawProvider,
  readTraceFixture,
  recordSql,
  useBaseTableReads,
  type TraceFixture,
} from './helpers/traceSnapshots'

const REVISION_3 = ['i_gen2_sdk_0_6_0', 'j_gen2_model_sdk_0_6_0', 'k_gen2_from_rev2']
const EDGE_REVISION_3 = 'i_gen2_sdk_0_6_0'
const EDGE_REVISION_2 = 'o_gen1_edge_sdk_0_5_0'
const SORTS: TraceSortColumn[] = ['created_at', 'execution_time', 'span_count']
const ORDERS = ['asc', 'desc'] as const
const TOLERANCE = 1e-12
const PAYLOAD_MARKER = new TextEncoder().encode(' of a long prompt\\nline ')

const listParams = (sort_by: TraceSortColumn, order: 'asc' | 'desc', limit?: number) => ({
  sort_by,
  order,
  search: '',
  filters: [] as string[],
  ...(limit ? { limit } : {}),
})

type FlatSpan = Omit<TraceSpan, 'children'>

/** `a` before `b` in the list order with `trace_id` in the same direction breaking ties. */
function compareTraces(sortBy: TraceSortColumn, order: 'asc' | 'desc') {
  const sign = order === 'asc' ? 1 : -1
  return (a: Trace, b: Trace) => {
    const left = a[sortBy]
    const right = b[sortBy]
    if (left !== right) return (left < right ? -1 : 1) * sign
    return (a.trace_id < b.trace_id ? -1 : a.trace_id > b.trace_id ? 1 : 0) * sign
  }
}

async function allPages(
  provider: ExperimentSnapshotDatabaseProvider,
  sortBy: TraceSortColumn,
  order: 'asc' | 'desc',
): Promise<Trace[]> {
  await provider.resetTracesRequestParams()
  const pages: Trace[] = []
  for (;;) {
    const page = await provider.getTraces(listParams(sortBy, order, 1))
    if (!page.length) return pages
    pages.push(...page)
  }
}

/** Full spans: the structure merged with each span's payload, as the UI shows them. */
async function mergedSpans(
  provider: ExperimentSnapshotDatabaseProvider,
  modelId: string,
  traceId: string,
): Promise<FlatSpan[]> {
  const spans = (await provider.getTraceSpans(modelId, traceId)) ?? []
  const merged = await Promise.all(
    spans.map(async (span) => {
      if (span.payloadLoaded) return span
      const payload = await provider.getSpanPayload(modelId, traceId, span.span_id)
      return { ...span, ...payload, payloadLoaded: true }
    }),
  )
  return merged.sort((a, b) => (a.span_id < b.span_id ? -1 : 1))
}

function treeShape(spans: TraceSpan[]): unknown[] {
  return spans.map((span) => [span.span_id, treeShape(span.children)])
}

function scoreMap(scores: ScoreInfo[]): Record<string, number> {
  return Object.fromEntries(scores.map((score) => [score.name, score.value]))
}

function expectScoresClose(actual: ScoreInfo[], expected: Record<string, number>): void {
  expect(actual.map((score) => score.name).sort()).toEqual(Object.keys(expected).sort())
  for (const score of actual) {
    const want = expected[score.name]!
    if (Number.isNaN(want)) expect(score.value).toBeNaN()
    else expect(Math.abs(score.value - want)).toBeLessThanOrEqual(TOLERANCE * Math.abs(want))
  }
}

const byName = (columns: TypedColumnInfo[]) =>
  [...columns].sort((a, b) => (a.name < b.name ? -1 : 1))

describe.each([EDGE_REVISION_3, EDGE_REVISION_2])('contract vectors of fixture %s', (name) => {
  const fixture: TraceFixture = readTraceFixture(name)
  const { traces, datasets } = fixture.expected
  let provider: ExperimentSnapshotDatabaseProvider

  beforeAll(async () => {
    provider = (await fixtureProvider(name)).provider
  })

  it('reads span trees and loads payloads per span only on revision 3', async () => {
    const structural = providerTraits(provider).structuralTraces
    expect(structural).toBe(name === EDGE_REVISION_3)
    for (const trace of traces) {
      const spans = (await provider.getTraceSpans(name, trace.trace_id))!
      expect(spans.map((span) => span.payloadLoaded)).toEqual(spans.map(() => !structural))
      if (structural) {
        expect(spans.every((span) => span.attributes === null && span.events === null)).toBe(true)
      }
      const tree = await provider.buildSpanTree(spans)
      expect(tree.map((span) => span.name)).toEqual([trace.root_span])
      expect(spans.map((span) => span.name).sort()).toEqual(trace.span_names)
      for (const span of await mergedSpans(provider, name, trace.trace_id)) {
        expect(span.dfs_span_type).toBe(trace.span_types[span.span_id])
        expect(span.status_message).toBe(trace.status_messages[span.span_id] ?? null)
        expect(span.events).toEqual(trace.events[span.span_id] ?? null)
        expect(span.links).toEqual(trace.links[span.span_id] ?? null)
      }
    }
  })

  it('returns the 200 KB attribute whole in the span payload', async () => {
    const large = fixture.expected.large_attribute!
    const payload = await provider.getSpanPayload(name, large.trace_id, large.span_id)
    const value = (payload.attributes as unknown as Record<string, string>)[large.key]!
    expect(value).toHaveLength(large.length)
    expect(createHash('sha256').update(value).digest('hex')).toBe(large.sha256)
    await expect(provider.getSpanPayload(name, large.trace_id, 'no-such-span')).rejects.toThrow(
      'Span not found',
    )
  })

  it.each(SORTS.flatMap((sort) => ORDERS.map((order) => [sort, order] as const)))(
    'lists traces by %s %s with trace_id breaking ties, page by page',
    async (sortBy, order) => {
      const all = await provider.getAllTraces(listParams(sortBy, order))
      expect(all.map((trace) => [trace.trace_id, trace.span_count, trace.execution_time])).toEqual(
        expect.arrayContaining(
          traces.map((trace) => [trace.trace_id, trace.span_count, trace.execution_time]),
        ),
      )
      expect(all.map((trace) => [trace.trace_id, trace.state, trace.evals])).toEqual(
        expect.arrayContaining(
          traces.map((trace) => [trace.trace_id, trace.state, trace.linked_evals]),
        ),
      )
      expect(all).toHaveLength(traces.length)
      const pages = await allPages(provider, sortBy, order)
      expect(pages.map((trace) => trace[sortBy])).toEqual(all.map((trace) => trace[sortBy]))
      if (providerTraits(provider).hasTraceSummaries) {
        expect(all).toEqual([...all].sort(compareTraces(sortBy, order)))
        expect(pages).toEqual(all)
      }
    },
  )

  it('has ties to break in the trace list', () => {
    const spanCounts = traces.map((trace) => trace.span_count)
    expect(new Set(spanCounts).size).toBeLessThan(spanCounts.length)
  })

  it('averages scores, skipping NaN, string and unparsable scores', async () => {
    for (const [datasetId, dataset] of Object.entries(datasets)) {
      const [averages] = await provider.getDatasetAverageScores(datasetId)
      expectScoresClose(averages!.scores, dataset.average_scores)
    }
  })

  it('returns the key catalogs of span attributes and eval columns', async () => {
    const attributeTypes = Object.fromEntries(
      (await provider.getTracesColumns(name)).attributes.map((column) => [
        column.name,
        column.type,
      ]),
    )
    expect(attributeTypes).toEqual(fixture.expected.span_attribute_keys)
    for (const [datasetId, dataset] of Object.entries(datasets)) {
      const columns = await provider.getEvalsColumns(datasetId)
      for (const [column, keys] of Object.entries(dataset.column_keys ?? {})) {
        const typed = columns[column as keyof typeof columns]
        expect(Object.fromEntries(typed.map((item) => [item.name, item.type]))).toEqual(keys)
      }
    }
  })

  it('links evals to traces both ways', async () => {
    for (const [datasetId, dataset] of Object.entries(datasets)) {
      const evalId = dataset.linked?.eval_id ?? dataset.eval_ids[0]!
      expect(await provider.getTraceId({ modelId: name, datasetId, evalId })).toBe(
        dataset.linked?.trace_id ?? null,
      )
    }
  })
})

describe.each(REVISION_3)(
  'revision 3 fixture %s: the new reads equal the base-table reads',
  (name) => {
    let derived: ExperimentSnapshotDatabaseProvider
    let base: ExperimentSnapshotDatabaseProvider
    const datasets = Object.keys(readTraceFixture(name).expected.datasets)

    beforeAll(async () => {
      derived = (await fixtureProvider(name)).provider
      base = (await fixtureProvider(name)).provider
      useBaseTableReads(base)
    })

    it('reads with every derived table of the export', () => {
      expect(providerTraits(derived)).toMatchObject({
        structuralTraces: true,
        hasTraceSummaries: true,
        hasScoreStats: true,
        hasKeyCatalogs: true,
      })
    })

    it.each(SORTS.flatMap((sort) => ORDERS.map((order) => [sort, order] as const)))(
      'lists the same traces by %s %s',
      async (sortBy, order) => {
        const statements = recordSql(derived)
        const fromSummaries = await derived.getAllTraces(listParams(sortBy, order))
        expect(statements.some((sql) => sql.includes('snapshot_trace_summaries'))).toBe(true)
        const fromSpans = await base.getAllTraces(listParams(sortBy, order))
        expect(fromSummaries).toEqual([...fromSpans].sort(compareTraces(sortBy, order)))
        const basePage = await base.getFreshTraces(listParams(sortBy, order, 2))
        const derivedPage = await derived.getFreshTraces(listParams(sortBy, order, 2))
        expect(derivedPage.map((trace) => trace[sortBy])).toEqual(
          basePage.map((trace) => trace[sortBy]),
        )
      },
    )

    it.each([
      ['span_count >= 2'],
      ['state = "ok"'],
      ['state IN ("ok", "error")'],
      ['execution_time > 300000000 AND span_count < 5'],
      ['created_at > "2000-01-01" OR trace_id LIKE "%1bf%"'],
      ['id != "0af7651916cd43dd8448eb211c80319c"'],
    ])('filters the summaries by trace columns: %s', async (filter) => {
      const statements = recordSql(derived)
      const params = { ...listParams('span_count', 'desc'), filters: [filter] }
      const fromSummaries = await derived.getAllTraces(params)
      expect(statements.some((sql) => sql.includes('snapshot_trace_summaries'))).toBe(true)
      const fromSpans = await base.getAllTraces(params)
      expect(fromSummaries).toEqual([...fromSpans].sort(compareTraces('span_count', 'desc')))
    })

    it('searches the summaries by trace id', async () => {
      const params = { ...listParams('execution_time', 'asc'), search: 'BF8' }
      const fromSummaries = await derived.getAllTraces(params)
      expect(fromSummaries.length).toBeGreaterThan(0)
      expect(fromSummaries).toEqual(await base.getAllTraces(params))
    })

    it.each([
      ['attributes.`user.city` = "東京"'],
      ['annotations.correct = "true"'],
      ['evals = "e1"'],
      ['span_count >= 2 AND attributes.`retry.count` > 1'],
    ])('falls back to the spans for filter %s', async (filter) => {
      const statements = recordSql(derived)
      const params = { ...listParams('created_at', 'asc'), filters: [filter] }
      const traces = await derived.getAllTraces(params)
      expect(statements.some((sql) => sql.includes('snapshot_trace_summaries'))).toBe(false)
      expect(traces).toEqual(await base.getAllTraces(params))
    })

    it('returns structural spans with the keys of full spans, payload fields null', async () => {
      const [trace] = await base.getAllTraces(listParams('created_at', 'asc'))
      const [full] = (await base.getTraceSpans(name, trace!.trace_id))!
      const structural = (await derived.getTraceSpans(name, trace!.trace_id))!.find(
        (span) => span.span_id === full!.span_id,
      )!
      expect(Object.keys(structural)).toEqual(Object.keys(full!))
      expect(structural).toEqual({
        ...full,
        attributes: null,
        events: null,
        links: null,
        status_message: null,
        payloadLoaded: false,
      })
    })

    it('builds the same trees, and the payloads complete the same spans', async () => {
      for (const trace of await base.getAllTraces(listParams('created_at', 'asc'))) {
        const baseSpans = (await base.getTraceSpans(name, trace.trace_id))!
        const derivedSpans = (await derived.getTraceSpans(name, trace.trace_id))!
        expect(treeShape(await derived.buildSpanTree(derivedSpans))).toEqual(
          treeShape(await base.buildSpanTree(baseSpans)),
        )
        expect(await mergedSpans(derived, name, trace.trace_id)).toEqual(
          await mergedSpans(base, name, trace.trace_id),
        )
      }
    })

    it('averages the same scores', async () => {
      for (const datasetId of datasets) {
        const [fromStats] = await derived.getDatasetAverageScores(datasetId)
        const [fromRows] = await base.getDatasetAverageScores(datasetId)
        expectScoresClose(fromStats!.scores, scoreMap(fromRows!.scores))
        const names = fromStats!.scores.map((score) => score.name)
        expect(names).toEqual([...names].sort())
      }
    })

    it('finds the same keys', async () => {
      const derivedColumns = await derived.getTracesColumns(name)
      const baseColumns = await base.getTracesColumns(name)
      expect(byName(derivedColumns.attributes)).toEqual(byName(baseColumns.attributes))
      expect(derivedColumns.annotations_feedback).toEqual(baseColumns.annotations_feedback)
      for (const datasetId of datasets) {
        const fromCatalog = await derived.getEvalsColumns(datasetId)
        const fromScan = await base.getEvalsColumns(datasetId)
        for (const column of Object.keys(fromScan) as (keyof typeof fromScan)[]) {
          expect(byName(fromCatalog[column])).toEqual(byName(fromScan[column]))
        }
      }
    })

    it('returns the same eval links and compare-mode rows', async () => {
      for (const datasetId of datasets) {
        const batch = { dataset_id: datasetId, limit: 2 }
        expect(await derived.getBatchExperimentEvals(batch)).toEqual(
          await base.getBatchExperimentEvals(batch),
        )
        for (const item of await base.getAllDatasetEvals({
          ...listParams('created_at', 'asc'),
          dataset_id: datasetId,
          sort_by: 'created_at',
        })) {
          const link = { modelId: name, datasetId, evalId: item.id }
          expect(await derived.getTraceId(link)).toBe(await base.getTraceId(link))
        }
      }
    })
  },
)

describe('a revision 3 snapshot missing derived tables', () => {
  let bytes: Uint8Array
  let reference: ExperimentSnapshotDatabaseProvider

  beforeAll(async () => {
    bytes = fixtureDatabase(EDGE_REVISION_3).bytes
    reference = await rawProvider('edge', bytes)
    useBaseTableReads(reference)
  })

  async function compareWith(provider: ExperimentSnapshotDatabaseProvider) {
    for (const sortBy of SORTS) {
      // Without summaries ties keep the order of the base-table query, which is undefined.
      const params = listParams(sortBy, 'desc')
      const sorted = (traces: Trace[]) => [...traces].sort(compareTraces(sortBy, 'desc'))
      expect(sorted(await provider.getAllTraces(params))).toEqual(
        sorted(await reference.getAllTraces(params)),
      )
    }
    for (const datasetId of Object.keys(readTraceFixture(EDGE_REVISION_3).expected.datasets)) {
      const [averages] = await provider.getDatasetAverageScores(datasetId)
      const [expected] = await reference.getDatasetAverageScores(datasetId)
      expectScoresClose(averages!.scores, scoreMap(expected!.scores))
      const columns = await provider.getEvalsColumns(datasetId)
      const expectedColumns = await reference.getEvalsColumns(datasetId)
      expect(byName(columns.scores)).toEqual(byName(expectedColumns.scores))
    }
    expect(byName((await provider.getTracesColumns('edge')).attributes)).toEqual(
      byName((await reference.getTracesColumns('edge')).attributes),
    )
  }

  it('reads the base tables when no snapshot_* table is left', async () => {
    const provider = await rawProvider(
      'edge',
      await editedDatabase(
        bytes,
        `DROP TABLE snapshot_trace_summaries; DROP TABLE snapshot_eval_score_stats;
         DROP TABLE snapshot_span_attribute_keys; DROP TABLE snapshot_eval_column_keys;`,
      ),
    )
    expect(providerTraits(provider)).toMatchObject({
      structuralTraces: true,
      hasTraceSummaries: false,
      hasScoreStats: false,
      hasKeyCatalogs: false,
    })
    await compareWith(provider)
  })

  it('reads summaries and score stats without key catalogs (export on SQLite before 3.45)', async () => {
    const provider = await rawProvider(
      'edge',
      await editedDatabase(
        bytes,
        'DROP TABLE snapshot_span_attribute_keys; DROP TABLE snapshot_eval_column_keys;',
      ),
    )
    expect(providerTraits(provider)).toMatchObject({
      hasTraceSummaries: true,
      hasScoreStats: true,
      hasKeyCatalogs: false,
    })
    const statements = recordSql(provider)
    await compareWith(provider)
    expect(statements.some((sql) => sql.includes('json_each'))).toBe(true)
    expect(statements.some((sql) => sql.includes('snapshot_eval_score_stats'))).toBe(true)
  })

  it('reads a NULL score sum as NaN', async () => {
    const provider = await rawProvider(
      'edge',
      await editedDatabase(
        bytes,
        `INSERT INTO snapshot_eval_score_stats VALUES ('edge_scores', 'diverged', 2, NULL)`,
      ),
    )
    const [averages] = await provider.getDatasetAverageScores('edge_scores')
    expect(scoreMap(averages!.scores).diverged).toBeNaN()
  })
})

// The export's summary statement (sdk `_snapshot_summaries.py`), to rebuild generated data.
const REBUILD_TRACE_SUMMARIES = `
  DELETE FROM snapshot_trace_summaries;
  INSERT INTO snapshot_trace_summaries
  SELECT trace_id, MIN(start_time_unix_nano), MAX(end_time_unix_nano),
    MAX(end_time_unix_nano) - MIN(start_time_unix_nano), COUNT(*),
    CASE
      WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) IS NULL THEN 3
      WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) = 2 THEN 2
      WHEN MAX(CASE WHEN parent_span_id IS NULL THEN status_code END) = 1 THEN 1
      ELSE 0
    END,
    MIN(created_at)
  FROM spans GROUP BY trace_id;
`

/** 120 traces whose durations, span counts, states and creation times repeat. */
function generatedSpans(): string {
  const rows: string[] = []
  for (let trace = 0; trace < 120; trace++) {
    const traceId = `gen${String((trace * 37) % 120).padStart(4, '0')}`
    const spans = 1 + (trace % 3)
    const start = 1_760_000_000_000_000_000 + trace * 1000
    for (let span = 0; span < spans; span++) {
      const parent = span ? `'${traceId}-0'` : 'NULL'
      const status = span ? 1 : trace % 4
      const created = `2026-01-0${1 + (trace % 4)} 10:00:0${span}`
      rows.push(
        `('${traceId}', '${traceId}-${span}', ${parent}, 'span', ${start + span}, ` +
          `${start + 1000 * (1 + (trace % 5))}, ${status}, '${created}')`,
      )
    }
  }
  return `INSERT INTO spans (trace_id, span_id, parent_span_id, name, start_time_unix_nano,
    end_time_unix_nano, status_code, created_at) VALUES ${rows.join(',\n')};`
}

describe('a generated revision 3 snapshot with many ties', () => {
  let derived: ExperimentSnapshotDatabaseProvider
  let base: ExperimentSnapshotDatabaseProvider

  beforeAll(async () => {
    const bytes = await editedDatabase(
      fixtureDatabase(EDGE_REVISION_3).bytes,
      generatedSpans() + REBUILD_TRACE_SUMMARIES,
    )
    derived = await rawProvider('generated', bytes)
    base = await rawProvider('generated', bytes)
    useBaseTableReads(base)
  })

  it.each(SORTS.flatMap((sort) => ORDERS.map((order) => [sort, order] as const)))(
    'pages by %s %s like the base-table query, with defined ties',
    async (sortBy, order) => {
      const fromSpans = await base.getAllTraces(listParams(sortBy, order))
      expect(await derived.getAllTraces(listParams(sortBy, order))).toEqual(
        [...fromSpans].sort(compareTraces(sortBy, order)),
      )
      const pages = await allPages(derived, sortBy, order)
      expect(pages).toEqual([...fromSpans].sort(compareTraces(sortBy, order)))
      await base.resetTracesRequestParams()
      const basePages = (await allPages(base, sortBy, order)).map((trace) => trace[sortBy])
      expect(pages.map((trace) => trace[sortBy])).toEqual(basePages)
    },
  )

  it.each([
    ['state = "error"'],
    ['state NOT IN ("ok", "in_progress")'],
    ['span_count = 2 AND execution_time <= 3000'],
    ['created_at >= "2026-01-03" OR id ILIKE "GEN001%"'],
  ])('filters like the base-table query: %s', async (filter) => {
    const params = { ...listParams('execution_time', 'asc'), filters: [filter], search: 'gen' }
    const fromSpans = await base.getAllTraces(params)
    expect(fromSpans.length).toBeGreaterThan(0)
    expect(await derived.getAllTraces(params)).toEqual(
      [...fromSpans].sort(compareTraces('execution_time', 'asc')),
    )
  })
})

describe('query plans on a revision 3 snapshot', () => {
  let provider: ExperimentSnapshotDatabaseProvider
  const plan = (sql: string, params: (string | number)[] = []) =>
    queryPlan(providerDatabase(provider), sql, params).join('\n')

  beforeAll(async () => {
    provider = (await fixtureProvider(EDGE_REVISION_3)).provider
  })

  it('reads the span tree from the covering index alone, without sorting', () => {
    const tree = plan(STRUCTURAL_SPANS_SQL, ['t'])
    expect(tree).toContain('COVERING INDEX spans_structure')
    expect(tree).not.toContain('TEMP B-TREE')
    expect(plan(SPAN_ANNOTATION_COUNTS_SQL, ['t'])).toContain(
      'COVERING INDEX span_annotations_span',
    )
    expect(
      plan(
        'SELECT attributes, events, links, status_message FROM spans WHERE trace_id = ? AND span_id = ?',
        ['t', 's'],
      ),
    ).toContain('sqlite_autoindex_spans_1 (trace_id=? AND span_id=?)')
  })

  it.each(SORTS.flatMap((sort) => ORDERS.map((order) => [sort, order] as const)))(
    'lists by %s %s from a summary index without sorting',
    (sortBy, order) => {
      const { sql, params } = traceSummariesQuery({
        sortBy,
        order: order === 'asc' ? 'ASC' : 'DESC',
        limit: 20,
        offset: 40,
      })
      const listPlan = plan(sql, params as (string | number)[])
      expect(listPlan).toContain('snapshot_trace_summaries')
      expect(listPlan).not.toContain('TEMP B-TREE')
    },
  )

  it('looks up eval links from the covering bridge indexes', () => {
    expect(plan(EVAL_TRACE_SQL, ['qa_set', 'e1'])).toContain(
      'COVERING INDEX eval_traces_bridge_eval',
    )
    expect(plan(TRACE_EVALS_SQL, ['t'])).toContain('COVERING INDEX eval_traces_bridge_trace')
    expect(
      plan('SELECT id FROM eval_annotations WHERE eval_id = ? AND dataset_id = ?', ['e1', 'qa']),
    ).toContain('INDEX eval_annotations_eval')
  })
})

describe('bytes read by range for the trace with the 200 KB attribute', () => {
  const fixture = readTraceFixture(EDGE_REVISION_3)
  const large = fixture.expected.large_attribute!
  const pageSize = fixture.page_size!
  let payloadPages: Set<number>

  beforeAll(() => {
    const { bytes } = fixtureDatabase(EDGE_REVISION_3)
    payloadPages = new Set()
    for (let page = 0; page * pageSize < bytes.length; page++) {
      const content = Buffer.from(bytes.subarray(page * pageSize, (page + 1) * pageSize))
      if (content.includes(PAYLOAD_MARKER)) payloadPages.add(page)
    }
  })

  async function session(baseReads = false) {
    const opened = await fixtureProvider(EDGE_REVISION_3, { chunkSize: pageSize })
    if (baseReads) useBaseTableReads(opened.provider)
    const { requests, memberOffset } = opened
    const pagesFrom = (from: number) => {
      const pages = new Set<number>()
      for (const request of requests.slice(from)) {
        const first = Math.floor((request.offset - memberOffset) / pageSize)
        const last = Math.floor((request.offset - memberOffset + request.length - 1) / pageSize)
        for (let page = first; page <= last; page++) pages.add(page)
      }
      return pages
    }
    const bytesFrom = (from: number) =>
      requests.slice(from).reduce((sum, request) => sum + request.length, 0)
    return { ...opened, pagesFrom, bytesFrom }
  }

  const listAndTree = async (provider: ExperimentSnapshotDatabaseProvider) => {
    await provider.getTraces(listParams('created_at', 'desc', 20))
    const spans = await provider.getTraceSpans(EDGE_REVISION_3, large.trace_id)
    await provider.buildSpanTree(spans!)
  }

  it('finds the payload pages in the fixture', () => {
    expect(payloadPages.size).toBeGreaterThanOrEqual(Math.floor(large.length / pageSize))
  })

  it('opens the list and the tree without the payload, and the span payload reads it', async () => {
    const { provider, requests, pagesFrom, bytesFrom } = await session()
    const opened = requests.length
    await listAndTree(provider)
    const listed = pagesFrom(opened)
    expect([...listed].filter((page) => payloadPages.has(page))).toEqual([])
    expect(listed.size).toBeLessThanOrEqual(LIST_AND_TREE_PAGE_BOUND)
    const listedBytes = bytesFrom(opened)
    expect(listedBytes).toBeLessThanOrEqual(LIST_AND_TREE_PAGE_BOUND * pageSize)

    const beforePayload = requests.length
    await provider.getSpanPayload(EDGE_REVISION_3, large.trace_id, large.span_id)
    const payloadRead = pagesFrom(beforePayload)
    expect([...payloadPages].every((page) => payloadRead.has(page))).toBe(true)
    expect(bytesFrom(beforePayload)).toBeGreaterThanOrEqual(large.length)
  })

  it('reads the payload pages with the base-table reads', async () => {
    const { provider, requests, pagesFrom } = await session(true)
    const opened = requests.length
    await listAndTree(provider)
    expect([...pagesFrom(opened)].filter((page) => payloadPages.has(page)).length).toBeGreaterThan(
      0,
    )
  })
})

// Measured: 7 pages of 16 KiB on fixture i (summary, trace, tree and bridge pages).
const LIST_AND_TREE_PAGE_BOUND = 10
