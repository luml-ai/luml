import { describe, expect, it } from 'vitest'
import type { TraceRow, TraceSpan } from '@/api/monitoring/interfaces'
import {
  buildSpanTree,
  countNewTraces,
  formatNanoTimestamp,
  getCollapsibleSpanIds,
  getNextTraceSort,
  getSpanBar,
} from '@/utils/traces'

function span(id: string, parent: string | null, start: number, end = start + 1): TraceSpan {
  return {
    trace_id: 't',
    span_id: id,
    parent_span_id: parent,
    name: id,
    kind: 0,
    start_time_unix_nano: start,
    end_time_unix_nano: end,
    status_code: null,
    status_message: null,
    attributes: {},
    events: [],
    links: [],
    dfs_span_type: null,
    annotation_count: 0,
  }
}

describe('buildSpanTree', () => {
  it('detaches spans that form a parent cycle', () => {
    const tree = buildSpanTree([span('a', 'b', 1), span('b', 'a', 2), span('c', 'a', 3)])
    expect(tree.map((node) => node.span_id)).toEqual(['a', 'b'])
    expect(tree[0]?.children.map((node) => node.span_id)).toEqual(['c'])
  })

  it('builds a very deep chain without overflowing the stack', () => {
    const depth = 50_000
    const spans = Array.from({ length: depth }, (_, index) =>
      span(`s${index}`, index ? `s${index - 1}` : null, index),
    )
    const tree = buildSpanTree(spans)
    expect(tree).toHaveLength(1)
    expect(getCollapsibleSpanIds(tree)).toHaveLength(depth - 1)
  })

  it('orders siblings by start time', () => {
    const tree = buildSpanTree([
      span('root', null, 0),
      span('late', 'root', 9),
      span('early', 'root', 1),
    ])
    expect(tree[0]?.children.map((node) => node.span_id)).toEqual(['early', 'late'])
  })
})

describe('getSpanBar', () => {
  it('keeps a visible minimum width for very short spans', () => {
    const bar = getSpanBar(span('s', null, 500, 501), { min: 0, max: 1_000_000 })
    expect(bar.end - bar.start).toBeGreaterThanOrEqual(1)
  })

  it('keeps a short span at the end of the trace inside the track', () => {
    const bar = getSpanBar(span('s', null, 1000, 1000), { min: 0, max: 1000 })
    expect(bar.end).toBe(100)
    expect(bar.start).toBe(99)
  })
})

describe('getNextTraceSort', () => {
  it('starts a newly selected column descending', () => {
    expect(getNextTraceSort({ field: 'ts', order: -1 }, 'latency_ms', 1)).toEqual({
      field: 'latency_ms',
      order: -1,
    })
  })

  it('toggles the active column', () => {
    expect(getNextTraceSort({ field: 'latency_ms', order: -1 }, 'latency_ms', 1)).toEqual({
      field: 'latency_ms',
      order: 1,
    })
  })
})

describe('countNewTraces', () => {
  const rows = ['n2', 'n1', 'old'].map((event_id) => ({ event_id }) as TraceRow)

  it('counts rows above the last seen top trace', () => {
    expect(countNewTraces(rows, 'old')).toBe(2)
  })

  it('treats a missing anchor as a full page of new traces', () => {
    expect(countNewTraces(rows, 'gone')).toBe(rows.length)
  })
})

describe('formatNanoTimestamp', () => {
  it('formats nanoseconds as an ISO timestamp with microseconds', () => {
    expect(formatNanoTimestamp(1_700_000_000_123_456_789)).toBe('2023-11-14T22:13:20.123457Z')
  })
})
