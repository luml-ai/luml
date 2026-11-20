import type { TraceSpan } from '@/interfaces/interfaces'

export function makeSpan(spanId: string, overrides: Partial<TraceSpan> = {}): TraceSpan {
  return {
    trace_id: 't1',
    span_id: spanId,
    parent_span_id: null,
    name: spanId,
    kind: 0,
    start_time_unix_nano: 0,
    end_time_unix_nano: 1000,
    status_code: null,
    status_message: null,
    attributes: '{}',
    events: null,
    links: null,
    children: [],
    dfs_span_type: null,
    annotation_count: null,
    payloadLoaded: true,
    ...overrides,
  }
}

/** One root with `groups` children of `perGroup` leaves each: 1 + groups * (perGroup + 1) spans. */
export function wideTree(groups: number, perGroup: number): TraceSpan[] {
  const root = makeSpan('root')
  for (let group = 0; group < groups; group++) {
    const child = makeSpan(`g${group}`, { parent_span_id: 'root' })
    for (let leaf = 0; leaf < perGroup; leaf++) {
      child.children.push(makeSpan(`g${group}-${leaf}`, { parent_span_id: child.span_id }))
    }
    root.children.push(child)
  }
  return [root]
}
