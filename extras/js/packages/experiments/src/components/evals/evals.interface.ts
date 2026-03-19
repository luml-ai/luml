import type {
  EvalsColumns,
  EvalsInfo,
  GetEvalsByDatasetParams,
  ModelsInfo,
} from '@/interfaces/interfaces'
import type { AnnotationSummary } from '@/components/annotations/annotations.interface'

export interface DatasetProps {
  data: EvalsInfo[]
  modelsInfo: ModelsInfo
  columns: EvalsColumns
  datasetId: string
}

export interface DatasetEmits {
  (e: 'get-next-page'): void
  (e: 'filter-change', filter: FilterInterface): void
  (e: 'sort', sortParams: SortParams): void
}

export interface FilterInterface {
  search: string
}

export interface DatasetListProps {
  modelsInfo: ModelsInfo
  loaderHeight: string
}

export interface DatasetData {
  columns: EvalsColumns
  data: EvalsInfo[]
  params: GetEvalsByDatasetParams
}

export interface TableEmits {
  (e: 'get-next-page'): void
  (e: 'sort', sortParams: SortParams): void
}

export interface TableProps {
  columnsTree: TableColumn[]
  data: EvalsInfo[]
  modelsInfo: ModelsInfo
  annotationsSummary: AnnotationSummary
  datasetId: string
}

export interface TableColumn {
  title: string
  children?: string[]
}

export interface ToolbarProps {
  columns: string[]
  selectedColumns: string[]
  exportLoading: boolean
}

export interface ToolbarEmits {
  (e: 'edit', list: string[]): void
  (e: 'export'): void
}

export interface SortParams {
  sortField: GetEvalsByDatasetParams['sort_by']
  sortOrder: 'asc' | 'desc'
}
