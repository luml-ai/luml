import type { AnnotationSummary } from '../annotations/annotations.interface'
import type { FilterItem } from '../table/filter/filter.interface'
import type { Trace } from '@/providers/ExperimentSnapshotApiProvider.interface'

export interface ToolbarProps {
  columns: string[]
  selectedColumns: string[]
}

export interface ToolbarEmits {
  (e: 'edit', list: string[]): void
  (e: 'export'): void
  (e: 'filter-change', filters: FilterItem[]): void
}

export interface TableProps {
  data: Trace[]
  selectedColumns: string[]
  artifactId: string
  annotationsSummary: AnnotationSummary
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
