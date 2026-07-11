import type { AnnotationSummaryExpectationItem } from '@/components/annotations/annotations.interface'

export type ExpectationColumnData = Omit<AnnotationSummaryExpectationItem, 'name'>

export interface ExpectationColumnProps {
  data: ExpectationColumnData | undefined
}
