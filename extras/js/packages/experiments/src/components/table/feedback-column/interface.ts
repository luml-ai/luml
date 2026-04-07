export interface FeedbackColumnData {
  positiveCount: number
  negativeCount: number
}

export interface FeedbackColumnProps {
  data: FeedbackColumnData | undefined
}
