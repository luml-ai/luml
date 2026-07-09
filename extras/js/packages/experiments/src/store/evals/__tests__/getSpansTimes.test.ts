import { describe, it, expect } from 'vitest'
import { getSpansTimes } from '../index'
import type { TraceSpan } from '@/interfaces/interfaces'

function makeSpan(start: number, end: number): Omit<TraceSpan, 'children'> {
  return {
    trace_id: 't1',
    span_id: `s-${start}-${end}`,
    parent_span_id: null,
    name: 'span',
    kind: 0,
    start_time_unix_nano: start,
    end_time_unix_nano: end,
    status_code: null,
    status_message: null,
    attributes: '{}',
    events: null,
    links: null,
    dfs_span_type: null,
    annotation_count: null,
  }
}

describe('getSpansTimes', () => {
  it('returns null bounds for an empty span list without leaking Infinity sentinels', () => {
    const { minTime, maxTime } = getSpansTimes([])

    expect(minTime).toBeNull()
    expect(maxTime).toBeNull()
    expect(minTime).not.toBe(Infinity)
    expect(maxTime).not.toBe(-Infinity)
  })

  it('derives the earliest start and latest end regardless of span order', () => {
    const spans = [makeSpan(300, 400), makeSpan(100, 250), makeSpan(200, 500)]

    expect(getSpansTimes(spans)).toEqual({ minTime: 100, maxTime: 500 })
  })

  it('treats a legitimate minimum of 0 as a real bound, not absent', () => {
    const spans = [makeSpan(0, 100), makeSpan(50, 200)]

    const { minTime, maxTime } = getSpansTimes(spans)

    expect(minTime).toBe(0)
    expect(maxTime).toBe(200)
  })
})
