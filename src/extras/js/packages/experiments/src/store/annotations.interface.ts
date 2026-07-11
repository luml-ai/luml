export interface AddEvalAnnotationParams {
  artifactId: string
  datasetId: string
  evalId: string
}

export interface AddSpanAnnotationParams {
  artifactId: string
  traceId: string
  spanId: string
}
