import { Bot, Circle, MessageSquareMore, Ruler, Shuffle, Wrench } from 'lucide-vue-next'
import {
  SectionState,
  SpanTypeEnum,
  type SortOrder,
  type TraceDetailResponse,
  type TraceRow,
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
  const roots: TraceSpanNode[] = []
  for (const node of nodes.values()) {
    const parent = node.parent_span_id ? nodes.get(node.parent_span_id) : undefined
    if (parent && !isInParentCycle(node, nodes)) parent.children.push(node)
    else roots.push(node)
  }
  return sortSpanNodes(roots)
}

function isInParentCycle(span: TraceSpan, spansById: Map<string, TraceSpan>): boolean {
  const visited = new Set<string>()
  let current = span.parent_span_id ? spansById.get(span.parent_span_id) : undefined
  while (current && !visited.has(current.span_id)) {
    if (current.span_id === span.span_id) return true
    visited.add(current.span_id)
    current = current.parent_span_id ? spansById.get(current.parent_span_id) : undefined
  }
  return false
}

function sortSpanNodes(nodes: TraceSpanNode[]): TraceSpanNode[] {
  return nodes
    .sort((a, b) => a.start_time_unix_nano - b.start_time_unix_nano)
    .map((node) => ({ ...node, children: sortSpanNodes(node.children) }))
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

export function getCollapsibleSpanIds(nodes: TraceSpanNode[]): string[] {
  return nodes.flatMap((node) =>
    node.children.length ? [node.span_id, ...getCollapsibleSpanIds(node.children)] : [],
  )
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
    { key: 'start_time_unix_nano', value: span.start_time_unix_nano },
    { key: 'end_time_unix_nano', value: span.end_time_unix_nano },
  ].filter((entry) => entry.value != null)
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

export function getTraceDetailEmptyState(response: TraceDetailResponse): EmptyStateContent | null {
  if (response.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Trace unavailable',
      detail: 'The monitoring store could not provide this inference call.',
    }
  }
  if (!response.trace) {
    return {
      title: 'Trace not found',
      detail: 'This inference call is no longer available in the selected window.',
    }
  }
  if (!response.trace.spans.length) {
    return {
      title: 'No spans recorded',
      detail: 'This inference call has no recorded spans.',
    }
  }
  return null
}
