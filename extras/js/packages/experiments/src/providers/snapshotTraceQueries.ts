import { SearchTracesUtils, type ComparisonDict, type FilterNode } from '@/utils/_search_utils'
import type { ScoreInfo } from '../interfaces/interfaces'
import type { SnapshotDatabase as Database, SqlValue } from './snapshot-source/SnapshotDatabase'

// SQL of the trace and eval reads that use what revision 3 snapshots add: the covering index
// `spans_structure`, the bridge and annotation indexes, and the `snapshot_*` tables built at
// export. Each read returns what the base-table query returns for the same data.

export type TraceSortColumn = 'created_at' | 'execution_time' | 'span_count'
export type EvalJsonColumn = 'inputs' | 'outputs' | 'refs' | 'scores' | 'metadata'

/** Satisfied by the covering index `spans_structure` alone: no payload column. */
export const STRUCTURAL_SPANS_SQL = `
  SELECT trace_id, span_id, parent_span_id, name, kind,
         start_time_unix_nano, end_time_unix_nano, status_code, dfs_span_type
  FROM spans
  WHERE trace_id = ?
  ORDER BY start_time_unix_nano, span_id
`

// The bridge indexes `(eval_id, eval_dataset_id, trace_id)` and `(trace_id, eval_id)` cover
// these lookups. Rowid order is the order a table scan returns, which is what snapshots
// without the indexes (revisions 0 to 2) return for the same SQL without ORDER BY.
export const EVAL_TRACE_SQL = `
  SELECT trace_id FROM eval_traces_bridge
  WHERE eval_dataset_id = ? AND eval_id = ?
  ORDER BY rowid
  LIMIT 1
`

export const TRACE_EVALS_SQL =
  'SELECT eval_id FROM eval_traces_bridge WHERE trace_id = ? ORDER BY rowid'

// The indexes below change the order the base-table queries read rows in. Revisions 0 to 2
// read these tables in rowid order, or evals in id order within a dataset, and the UI shows
// what that order gives: ties, first-seen keys and the value or type of the first row.

/** Within a name, annotations in rowid order instead of span order. */
export const TRACE_ANNOTATIONS_SQL = `
  SELECT name, value, annotation_kind, value_type
  FROM span_annotations
  WHERE trace_id = ?
  ORDER BY name, rowid
`

/** The distinct fields in order of their first annotation instead of eval order. */
export const EVAL_ANNOTATION_FIELDS_SQL = `
  SELECT name, value_type FROM eval_annotations
  WHERE annotation_kind = ? AND dataset_id = ?
  GROUP BY name, value_type
  ORDER BY MIN(rowid)
`

export const DATASET_EVAL_IDS_SQL = 'SELECT id FROM evals WHERE dataset_id = ? ORDER BY id'

export const SPAN_ANNOTATION_COUNTS_SQL = `
  SELECT span_id, COUNT(*) FROM span_annotations WHERE trace_id = ? GROUP BY span_id
`

export const SCORE_STATS_SQL = `
  SELECT score_key, sum, count FROM snapshot_eval_score_stats
  WHERE dataset_id = ?
  ORDER BY score_key
`

export const SPAN_ATTRIBUTE_KEYS_SQL =
  'SELECT key, type FROM snapshot_span_attribute_keys ORDER BY key'

export const EVAL_COLUMN_KEYS_SQL = `
  SELECT key, type FROM snapshot_eval_column_keys
  WHERE dataset_id = ? AND column_name = ?
  ORDER BY key
`

function selectRows(database: Database, sql: string, params: SqlValue[]): SqlValue[][] {
  const statement = database.prepare(sql)
  try {
    statement.bind(params)
    const rows: SqlValue[][] = []
    while (statement.step()) rows.push(statement.get())
    return rows
  } finally {
    statement.free()
  }
}

/** A span as the tree needs it: payload fields null, to be fetched with `getSpanPayload`. */
export type StructuralSpan = Record<string, SqlValue | boolean>

/**
 * The spans of one trace without payloads, plus the annotation count per span from one
 * grouped query instead of one count per span.
 */
export function readStructuralSpans(
  database: Database,
  traceId: string,
  hasSpanAnnotations: boolean,
): StructuralSpan[] {
  const counts = new Map<SqlValue, number>()
  if (hasSpanAnnotations) {
    for (const [spanId, count] of selectRows(database, SPAN_ANNOTATION_COUNTS_SQL, [traceId])) {
      counts.set(spanId ?? null, Number(count))
    }
  }
  return selectRows(database, STRUCTURAL_SPANS_SQL, [traceId]).map((row) => {
    const [trace_id, span_id, parent_span_id, name, kind, start, end, status_code, span_type] = row
    // The keys of the full read in its order, so either path renders the same.
    return {
      trace_id: trace_id ?? null,
      span_id: span_id ?? null,
      parent_span_id: parent_span_id ?? null,
      name: name ?? null,
      kind: kind ?? null,
      start_time_unix_nano: start ?? null,
      end_time_unix_nano: end ?? null,
      status_code: status_code ?? null,
      status_message: null,
      attributes: null,
      events: null,
      links: null,
      dfs_span_type: span_type ?? null,
      annotation_count: counts.get(span_id ?? null) ?? 0,
      payloadLoaded: false,
    }
  })
}

// Derived from the parser instead of copied, so a renamed identifier type cannot drift.
const TRACE_COLUMN_TYPE = (
  SearchTracesUtils.parseSearchFilter('span_count = 0')[0] as ComparisonDict
).type

function onlyTraceColumns(nodes: FilterNode[]): boolean {
  return nodes.every((node) => {
    if ('operator' in node) return true
    if ('group' in node) return onlyTraceColumns(node.group)
    return node.type === TRACE_COLUMN_TYPE
  })
}

/**
 * True when `snapshot_trace_summaries` can answer the filters: each one compares only trace
 * columns. Span attribute, annotation and evals filters need the base tables.
 */
export function summariesAnswerTraceFilters(filters: string[] | undefined): boolean {
  return (filters ?? []).every((filter) =>
    onlyTraceColumns(SearchTracesUtils.parseSearchFilter(filter)),
  )
}

export interface TraceSummariesRequest {
  sortBy: TraceSortColumn
  order: 'ASC' | 'DESC'
  search?: string
  filters?: string[]
  limit?: number
  offset: number
}

/**
 * The trace list from the export's summaries. The base-table query orders by the sort column
 * alone, so its ties have no defined order; here `trace_id` in the same direction breaks them,
 * which the summary indexes `(column, trace_id)` serve without a sort.
 */
export function traceSummariesQuery(request: TraceSummariesRequest): {
  sql: string
  params: SqlValue[]
} {
  const whereParts: string[] = []
  const params: SqlValue[] = []
  if (request.search) {
    whereParts.push('trace_id LIKE ?')
    params.push(`%${request.search}%`)
  }
  for (const filter of request.filters ?? []) {
    // The trace columns are columns of the summary table, so the HAVING clause of the
    // base-table query works here as WHERE.
    const [sql, filterParams] = SearchTracesUtils.toSql(filter)
    if (!sql) continue
    whereParts.push(sql)
    params.push(...(filterParams as SqlValue[]))
  }
  if (request.limit) params.push(request.limit)
  if (request.offset) params.push(request.offset)
  const sql = `
    SELECT trace_id, execution_time, span_count, created_at, state
    FROM snapshot_trace_summaries
    ${whereParts.length ? `WHERE ${whereParts.join(' AND ')}` : ''}
    ORDER BY ${request.sortBy} ${request.order}, trace_id ${request.order}
    ${request.limit ? 'LIMIT ?' : ''}
    ${request.offset ? 'OFFSET ?' : ''}
  `
  return { sql, params }
}

/**
 * Averages from `snapshot_eval_score_stats`, by key name. A NULL sum is SQLite's NaN (a sum of
 * infinities of both signs), which the per-row average also gives.
 */
export function readScoreStats(database: Database, datasetId: string): ScoreInfo[] {
  return selectRows(database, SCORE_STATS_SQL, [datasetId]).map(([key, sum, count]) => ({
    name: String(key),
    value: sum === null ? NaN : Number(sum) / Number(count),
  }))
}

export function readSpanAttributeKeys(database: Database): [SqlValue, SqlValue][] {
  return selectRows(database, SPAN_ATTRIBUTE_KEYS_SQL, []).map(([key, type]) => [
    key ?? null,
    type ?? null,
  ])
}

export function readEvalColumnKeys(
  database: Database,
  datasetId: string,
  column: EvalJsonColumn,
): [SqlValue, SqlValue][] {
  return selectRows(database, EVAL_COLUMN_KEYS_SQL, [datasetId, column]).map(([key, type]) => [
    key ?? null,
    type ?? null,
  ])
}
