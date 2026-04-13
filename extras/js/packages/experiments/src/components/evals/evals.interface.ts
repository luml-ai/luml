import type {
  EvalsInfo,
  GetEvalsByDatasetParams,
  ModelsInfo,
  TypedColumnInfo,
  TypedEvalsColumns,
} from '@experiments/interfaces/interfaces'
import type { AnnotationSummary } from '@experiments/components/annotations/annotations.interface'

export interface DatasetProps {
  data: EvalsInfo[]
  modelsInfo: ModelsInfo
  columns: TypedEvalsColumns
  datasetId: string
}

export interface DatasetEmits {
  (e: 'get-next-page'): void
  (e: 'filter-change', filter: FilterInterface): void
  (e: 'sort', sortParams: SortParams): void
}

export interface FilterInterface {
  search: string
  filters: string[]
}

export interface DatasetListProps {
  modelsInfo: ModelsInfo
  loaderHeight: string
  emptyMessage?: string
}

export interface DatasetData {
  columns: TypedEvalsColumns
  data: EvalsInfo[]
  params: GetEvalsByDatasetParams
}

export interface TableEmits {
  (e: 'get-next-page'): void
  (e: 'sort', sortParams: SortParams): void
  (e: 'filters-change', filters: string[]): void
}

export interface TableProps {
  columnsTree: TableColumn[]
  data: EvalsInfo[]
  modelsInfo: ModelsInfo
  annotationsSummary: AnnotationSummary
  datasetId: string
  typedColumns: TypedColumnInfo[]
  filters: string[]
}

export interface TableColumn {
  title: string
  children?: string[]
}

export interface ToolbarProps {
  columns: string[]
  typedColumns: TypedColumnInfo[]
  selectedColumns: string[]
  exportLoading: boolean
}

export interface ToolbarEmits {
  (e: 'edit', list: string[]): void
  (e: 'export'): void
  (e: 'filters-change', filters: string[]): void
}

export interface SortParams {
  sortField: GetEvalsByDatasetParams['sort_by']
  sortOrder: 'asc' | 'desc'
}
