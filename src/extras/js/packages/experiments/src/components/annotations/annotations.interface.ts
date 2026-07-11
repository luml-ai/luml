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

export interface AnnotationSummaryFeedbackItem {
  name: string
  total: number
  counts: Record<string, number>
}

export interface AnnotationSummaryExpectationItem {
  name: string
  total: number
  positive: number
  negative: number
  value: string | number | null
}

export type AddAnnotationPayload = Omit<Annotation, 'id' | 'created_at' | 'user'>

export type UpdateAnnotationPayload = Omit<
  AddAnnotationPayload,
  'name' | 'annotation_kind' | 'value_type' | 'user' | 'created_at'
>

export interface AnnotationFormInterface {
  type: AnnotationKind
  name: string
  dataType: AnnotationValueType
  value: number | boolean | string
  rationale: string
}
