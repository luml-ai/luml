export type TableSortOrder = 1 | -1

export const TRACES_PAGE_SIZE = 20

export const DEFAULT_TRACES_SORT_FIELD = 'ts'
export const DEFAULT_TRACES_SORT_ORDER: TableSortOrder = -1

export const TRACES_COLUMN_WIDTHS = {
  ts: 160,
  request: 220,
  features: 220,
  prediction: 220,
  status: 180,
  latency: 160,
}

export const TRACE_DIALOG_GAP = 15

export enum TraceDetailTab {
  ATTRIBUTES = 'attributes',
  EVENTS = 'events',
  METADATA = 'metadata',
}

export const TRACE_DETAIL_TABS = [
  { value: TraceDetailTab.ATTRIBUTES, label: 'Attributes' },
  { value: TraceDetailTab.EVENTS, label: 'Events' },
  { value: TraceDetailTab.METADATA, label: 'Metadata' },
]
