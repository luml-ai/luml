import type { FilterItem } from '../table/filter/filter.interface'

export interface ToolbarProps {
  columns: string[]
  selectedColumns: string[]
  exportLoading: boolean
}

export interface ToolbarEmits {
  (e: 'edit', list: string[]): void
  (e: 'export'): void
  (e: 'filter-change', filters: FilterItem[]): void
}

export interface TableProps {
  data: Record<string, any>[]
  selectedColumns: string[]
  artifactId: string
}

export interface TableEmits {
  (e: 'get-next-page'): void
  (e: 'sort', sortParams: SortParams): void
}

export interface SortParams {
  sortField: 'created_at' | 'execution_time' | 'span_count'
  sortOrder: 'asc' | 'desc'
}

export interface TracesWrapperProps {
  artifactId: string
}
