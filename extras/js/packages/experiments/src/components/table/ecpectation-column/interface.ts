import type { AnnotationSummaryExpectationItem } from '@experiments/components/annotations/annotations.interface'

export type ExpectationColumnData = Omit<AnnotationSummaryExpectationItem, 'name'>

export interface ExpectationColumnProps {
  data: ExpectationColumnData | undefined
}
