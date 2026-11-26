import { Bot, Circle, MessageSquareMore, Ruler, Shuffle, Wrench } from 'lucide-vue-next'
import {
  SectionState,
  SpanTypeEnum,
  type SortOrder,
  type TraceDetailResponse,
  type TraceRow,
  type Dimensions,
  type TraceSortKey,
  type TraceSpan,
  type TraceSpanNode,
  type TracesResponse,
} from '@/api/monitoring/interfaces'
import type { EmptyStateContent } from '@/types/empty'
import type { SpanTypeData, TraceEntry, TraceSpanRange } from '@/types/traces'
import {
  DEFAULT_TRACES_SORT_FIELD,
  DEFAULT_TRACES_SORT_ORDER,
  MIN_SPAN_BAR_PERCENT,
  NEW_SORT_FIELD_ORDER,
  SPAN_STATUS_ERROR,
  type TableSortOrder,
} from '@/constants/traces'
import { isFailedOutcome } from '@/utils/runtime'

export function getTraceStatusSeverity(
  row: Pick<TraceRow, 'status' | 'status_code'>,
): 'success' | 'warn' | 'danger' {
  if (!isFailedOutcome(row)) return 'success'
  if (row.status_code >= 400 && row.status_code < 500) return 'warn'
  return 'danger'
}

export function toTraceSortKey(field: string): TraceSortKey {
  if (field === 'latency_ms') return 'latency'
  if (field === 'status') return 'status'
  return 'ts'
}

export function toSortOrder(order: TableSortOrder): SortOrder {
  return order === 1 ? 'asc' : 'desc'
}

export function normalizeTraceSort(
  field: unknown,
  order: number | null | undefined,
): { field: string; order: TableSortOrder } {
  if (typeof field !== 'string' || !field || (order !== 1 && order !== -1)) {
    return { field: DEFAULT_TRACES_SORT_FIELD, order: DEFAULT_TRACES_SORT_ORDER }
  }
  return { field, order }
}

export interface TracesQuery {
  dimensions: Dimensions
  first: number
  sort: { field: string; order: TableSortOrder }
}

export function isSameTracesQuery(a: TracesQuery, b: TracesQuery): boolean {
  return (
    a.dimensions === b.dimensions &&
    a.first === b.first &&
    a.sort.field === b.sort.field &&
    a.sort.order === b.sort.order
  )
}

export function isLatestTracesQuery(query: TracesQuery): boolean {
  return (
    query.first === 0 &&
    query.sort.field === DEFAULT_TRACES_SORT_FIELD &&
    query.sort.order === DEFAULT_TRACES_SORT_ORDER
  )
}

export function getNextTraceSort(
  current: { field: string; order: TableSortOrder },
  field: unknown,
  order: number | null | undefined,
): { field: string; order: TableSortOrder } {
  if (typeof field === 'string' && field && field !== current.field) {
    return { field, order: NEW_SORT_FIELD_ORDER }
  }
  return normalizeTraceSort(field, order)
}

export function getFreshTraceIds(rows: TraceRow[], previousIds: ReadonlySet<string>): Set<string> {
  return new Set(rows.filter((row) => !previousIds.has(row.event_id)).map((row) => row.event_id))
}

export function countNewTraces(latestRows: TraceRow[], topEventId: string): number {
  const index = latestRows.findIndex((row) => row.event_id === topEventId)
  return index === -1 ? latestRows.length : index
}

export function formatNewTracesLabel(count: number, pageSize: number): string {
  const amount = count >= pageSize ? `${pageSize}+` : String(count)
  return `${amount} new ${count === 1 ? 'trace' : 'traces'} — show latest`
}

export function getTracesEmptyState(traces: TracesResponse): EmptyStateContent | null {
  if (traces.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Traces unavailable',
      detail: 'The monitoring store could not provide inference calls for this window.',
    }
  }
  if (traces.state === SectionState.EMPTY || traces.total === 0) {
    return {
      title: 'No inference calls in this window',
      detail: 'Recent prediction requests will appear here once the deployment serves traffic.',
    }
  }
  return null
}

export function clampTracesOffset(offset: number, total: number | null): number {
  return total !== null && offset >= total ? 0 : offset
}

export function buildSpanTree(spans: TraceSpan[]): TraceSpanNode[] {
  const nodes = new Map<string, TraceSpanNode>(
    spans.map((span) => [span.span_id, { ...span, children: [] }]),
  )
  const cycleIds = getParentCycleIds(nodes)
  const roots: TraceSpanNode[] = []
  for (const node of nodes.values()) {
    const parent = node.parent_span_id ? nodes.get(node.parent_span_id) : undefined
    if (parent && !cycleIds.has(node.span_id)) parent.children.push(node)
    else roots.push(node)
  }
  return sortSpanNodes(roots)
}

function getParentCycleIds(nodes: Map<string, TraceSpan>): Set<string> {
  const visited = new Set<string>()
  const cycleIds = new Set<string>()
  for (const startId of nodes.keys()) {
    const path: string[] = []
    const onPath = new Set<string>()
    let id: string | null | undefined = startId
    while (id && nodes.has(id) && !visited.has(id)) {
      visited.add(id)
      onPath.add(id)
      path.push(id)
      id = nodes.get(id)?.parent_span_id
    }
    if (id && onPath.has(id)) {
      path.slice(path.indexOf(id)).forEach((cycleId) => cycleIds.add(cycleId))
    }
  }
  return cycleIds
}

function compareSpanStart(a: TraceSpanNode, b: TraceSpanNode): number {
  return a.start_time_unix_nano - b.start_time_unix_nano
}

function sortSpanNodes(roots: TraceSpanNode[]): TraceSpanNode[] {
  const stack = [roots]
  for (let nodes = stack.pop(); nodes; nodes = stack.pop()) {
    nodes.sort(compareSpanStart)
    for (const node of nodes) if (node.children.length) stack.push(node.children)
  }
  return roots
}

export function getSpanRange(spans: TraceSpan[]): TraceSpanRange {
  if (!spans.length) return { min: null, max: null }
  return {
    min: Math.min(...spans.map((span) => span.start_time_unix_nano)),
    max: Math.max(...spans.map((span) => span.end_time_unix_nano)),
  }
}

export function getSpanProgress(time: number, range: TraceSpanRange, fallback: number): number {
  if (range.min === null || range.max === null) return fallback
  const total = range.max - range.min
  if (total <= 0) return fallback
  const percent = ((time - range.min) / total) * 100
  return Math.min(100, Math.max(0, percent))
}

export function getSpanBar(span: TraceSpan, range: TraceSpanRange): { start: number; end: number } {
  const start = getSpanProgress(span.start_time_unix_nano, range, 0)
  const end = getSpanProgress(span.end_time_unix_nano, range, 100)
  const width = Math.max(end - start, MIN_SPAN_BAR_PERCENT)
  const boundedStart = Math.min(start, 100 - width)
  return { start: boundedStart, end: boundedStart + width }
}

export function getCollapsibleSpanIds(nodes: TraceSpanNode[]): string[] {
  const ids: string[] = []
  const stack = [...nodes]
  for (let node = stack.pop(); node; node = stack.pop()) {
    if (!node.children.length) continue
    ids.push(node.span_id)
    stack.push(...node.children)
  }
  return ids
}

export function isFailedSpan(span: TraceSpan): boolean {
  return span.status_code === SPAN_STATUS_ERROR
}

export function getSpanTypeData(type: SpanTypeEnum | null): SpanTypeData {
  switch (type) {
    case SpanTypeEnum.AGENT:
      return { icon: Bot, color: 'var(--p-trace-span-icon-color-6)' }
    case SpanTypeEnum.CHAT:
      return { icon: MessageSquareMore, color: 'var(--p-trace-span-icon-color-2)' }
    case SpanTypeEnum.TOOL:
      return { icon: Wrench, color: 'var(--p-trace-span-icon-color-3)' }
    case SpanTypeEnum.EMBEDDER:
      return { icon: Ruler, color: 'var(--p-trace-span-icon-color-4)' }
    case SpanTypeEnum.RERANKER:
      return { icon: Shuffle, color: 'var(--p-trace-span-icon-color-5)' }
    default:
      return { icon: Circle, color: 'var(--p-trace-span-icon-color-1)' }
  }
}

export function formatSpanDuration(span: TraceSpan): string {
  return formatNanoseconds(span.end_time_unix_nano - span.start_time_unix_nano)
}

export function formatNanoseconds(ns: number): string {
  if (ns < 1_000) return '<1µs'
  const micros = Math.round(ns / 1_000)
  if (micros < 1_000) return `${micros}µs`
  const millis = Math.round(ns / 1_000_000)
  if (millis < 1_000) return `${millis}ms`
  const seconds = (ns / 1_000_000_000).toFixed(2)
  if (Number(seconds) < 60) return `${seconds}s`
  const totalSeconds = Math.round(ns / 1_000_000_000)
  const minutes = Math.floor(totalSeconds / 60)
  if (minutes < 60) return `${minutes}min ${totalSeconds % 60}s`
  const hours = Math.floor(minutes / 60)
  return `${hours}h ${minutes % 60}min`
}

export function shortenId(id: string, head = 8, tail = 7): string {
  if (id.length <= head + tail + 3) return id
  return `${id.slice(0, head)}...${id.slice(-tail)}`
}

export function getSortedEntries(value: Record<string, unknown> | null | undefined): TraceEntry[] {
  if (!value) return []
  return Object.entries(value)
    .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true, sensitivity: 'base' }))
    .map(([key, item]) => ({ key, value: item }))
}

export function getEventEntries(events: unknown[]): TraceEntry[] {
  return events.map((event, index) => ({ key: getEventName(event, index), value: event }))
}

function getEventName(event: unknown, index: number): string {
  if (event && typeof event === 'object' && 'name' in event && typeof event.name === 'string') {
    return event.name
  }
  return `Event ${index + 1}`
}

export function getSpanMetadata(span: TraceSpan): TraceEntry[] {
  return [
    { key: 'trace_id', value: span.trace_id },
    { key: 'span_id', value: span.span_id },
    { key: 'parent_span_id', value: span.parent_span_id },
    { key: 'kind', value: span.kind },
    { key: 'status_code', value: span.status_code },
    { key: 'status_message', value: span.status_message },
    { key: 'start_time', value: formatNanoTimestamp(span.start_time_unix_nano) },
    { key: 'end_time', value: formatNanoTimestamp(span.end_time_unix_nano) },
  ].filter((entry) => entry.value != null)
}

export function formatNanoTimestamp(ns: number): string {
  const micros = Math.round(ns / 1_000)
  const millis = Math.floor(micros / 1_000)
  const date = new Date(millis)
  if (Number.isNaN(date.getTime())) return String(ns)
  const fraction = String(micros - millis * 1_000).padStart(3, '0')
  return date.toISOString().replace('Z', `${fraction}Z`)
}

export function formatTraceValue(value: unknown): string {
  if (typeof value === 'string') return value
  if (value === undefined) return ''
  return JSON.stringify(value, null, 2) ?? String(value)
}

export function getTraceValueStats(text: string): string | null {
  const lines = text.split('\n').length
  if (lines <= 1) return null
  return `${lines} lines · ${text.length} chars`
}

export const TRACE_NOT_FOUND_STATE: EmptyStateContent = {
  title: 'Trace not found',
  detail:
    'This inference call is no longer in the selected window. Widen the time window to inspect it.',
}

export function getTraceDetailEmptyState(response: TraceDetailResponse): EmptyStateContent | null {
  if (response.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Trace unavailable',
      detail: 'The monitoring store could not provide this inference call.',
    }
  }
  if (!response.trace) return TRACE_NOT_FOUND_STATE
  if (!response.trace.spans.length) {
    return {
      title: 'No spans recorded',
      detail: 'This inference call has no recorded spans.',
    }
  }
  return null
}
