export type TableSortOrder = 1 | -1

export const TRACES_PAGE_SIZE = 20

export const DEFAULT_TRACES_SORT_FIELD = 'ts'
export const DEFAULT_TRACES_SORT_ORDER: TableSortOrder = -1

export const NEW_SORT_FIELD_ORDER: TableSortOrder = -1

export const TRACES_PAGINATOR_TEMPLATE =
  'FirstPageLink PrevPageLink PageLinks NextPageLink LastPageLink CurrentPageReport'

export const TRACES_PAGE_REPORT_TEMPLATE = '{first}–{last} of {totalRecords}'

export const TRACES_COLUMN_WIDTHS = {
  ts: 160,
  request: 220,
  features: 220,
  prediction: 220,
  status: 180,
  latency: 160,
}

export const TRACE_DIALOG_GAP = 15

export const NOT_FOUND_STATUS = 404

export const MIN_SPAN_BAR_PERCENT = 1

export const SPAN_STATUS_ERROR = 2

export const TRACES_SORT_STORAGE_KEY = 'monitoring:traces-sort'

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
