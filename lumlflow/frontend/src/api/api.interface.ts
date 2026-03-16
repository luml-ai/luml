export interface PaginatedResponse<T> {
  items: T[]
  cursor: string | null
}

export interface GetGroupsParams {
  limit: number
  cursor: string | null
  sort_by: 'name' | 'created_at' | 'description'
  order: 'asc' | 'desc'
  search: string | null
}

export interface GetExperimentsParams {
  group_id: string
  limit: number
  cursor: string | null
  search: string | null
}

export interface GetExperimentTracesParams {
  experiment_id: string
  limit?: number
  cursor?: string | null
  sort_by?: 'execution_time' | 'span_count' | 'created_at'
  order?: 'asc' | 'desc'
  search?: string
}

export interface UpdateModelPayload {
  name: string | null
  tags: string[] | null
}

export interface CheckAuthResponse {
  has_key: boolean
}

export interface GetExperimentEvalsParams {
  experiment_id: string
  limit: number
  cursor?: string | null
  sort_by: 'created_at'
  order: 'asc' | 'desc'
  search: string
  dataset_id: string
}

export interface AverageScore {
  name: string
  value: number
}

export enum AnnotationKind {
  FEEDBACK = 'feedback',
  EXPECTATION = 'expectation',
}

export enum AnnotationValueType {
  INT = 'int',
  BOOL = 'bool',
  STRING = 'string',
}

export interface Annotation {
  id: string
  name: string
  annotation_kind: AnnotationKind
  value_type: AnnotationValueType
  value: number | boolean | string
  user: string
  created_at: string
  rationale: string | null
}

export interface AnnotationSummary {
  feedback: AnnotationSummaryFeedbackItem[]
  expectations: AnnotationSummaryExpectationItem[]
}

interface AnnotationSummaryFeedbackItem {
  name: string
  total: number
  counts: Record<string, number>
}

interface AnnotationSummaryExpectationItem {
  name: string
  total: number
  positive: number
  negative: number
  firstValue: string | number | null
}

export type AddAnnotationPayload = Omit<Annotation, 'id' | 'created_at'>

export type UpdateAnnotationPayload = Omit<
  AddAnnotationPayload,
  'name' | 'annotation_kind' | 'value_type' | 'user' | 'created_at'
>
