import type { Annotation, AnnotationSummary } from '@experiments/components/annotations/annotations.interface'
import type {
  EvalsInfo,
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  GetEvalsByDatasetParams,
  GetTracesParams,
  ModelScores,
  SpansListType,
  TypedEvalsColumns,
  SpansParams,
  TraceSpan,
  TypedTracesColumns,
  ValidateResponseItem,
} from '../interfaces/interfaces'
import type { Trace } from './ExperimentSnapshotApiProvider.interface'

export class ExperimentSnapshotWorkerProxy implements ExperimentSnapshotProvider {
  constructor(private worker: Worker) {}

  private call<T>(method: string, args?: any[], signal?: AbortSignal): Promise<T> {
    const requestId = crypto.randomUUID()

    return new Promise((resolve, reject) => {
      const handler = (e: MessageEvent) => {
        if (e.data.requestId !== requestId) return
        cleanup()
        if (e.data.type === 'error') {
          reject(e.data.error)
        } else {
          resolve(e.data.data)
        }
      }

      const onAbort = () => {
        cleanup()
        this.worker.postMessage({
          type: 'cancel',
          requestId,
        })
        reject(new DOMException('Aborted', 'AbortError'))
      }

      const cleanup = () => {
        this.worker.removeEventListener('message', handler)
        signal?.removeEventListener('abort', onAbort)
      }

      this.worker.addEventListener('message', handler)

      if (signal) {
        if (signal.aborted) {
          onAbort()
          return
        }
        signal.addEventListener('abort', onAbort)
      }

      this.worker.postMessage({
        type: 'call',
        requestId,
        payload: { method, args },
      })
    })
  }

  init(data: any) {
    return this.call<void>('init', [data])
  }

  getStaticParamsList(signal?: AbortSignal) {
    return this.call<ExperimentSnapshotStaticParams[]>('getStaticParamsList', undefined, signal)
  }

  getDynamicMetricsNames(signal?: AbortSignal) {
    return this.call<string[]>('getDynamicMetricsNames', undefined, signal)
  }

  getDynamicMetricData(metricName: string, signal?: AbortSignal) {
    return this.call<ExperimentSnapshotDynamicMetric[]>(
      'getDynamicMetricData',
      [metricName],
      signal,
    )
  }

  buildSpanTree(spans: Omit<TraceSpan, 'children'>[]) {
    return this.call<TraceSpan[]>('buildSpanTree', [spans])
  }

  getTraceId(args: SpansParams) {
    return this.call<string>('getTraceId', [args])
  }

  getTraceSpans(modelId: string, traceId: string) {
    return this.call<SpansListType>('getTraceSpans', [modelId, traceId])
  }

  getEvalsColumns(datasetId: string, signal?: AbortSignal) {
    return this.call<TypedEvalsColumns>('getEvalsColumns', [datasetId], signal)
  }

  getUniqueDatasetsIds(signal?: AbortSignal) {
    return this.call<string[]>('getUniqueDatasetsIds', undefined, signal)
  }

  resetEvalsDatasetsRequestParams() {
    return this.call<void>('resetEvalsDatasetsRequestParams', undefined)
  }

  resetDatasetPage(datasetId: string) {
    return this.call<void>('resetDatasetPage', [datasetId])
  }

  getDatasetAverageScores(datasetId: string) {
    return this.call<ModelScores[]>('getDatasetAverageScores', [datasetId])
  }

  getNextEvalsByDatasetId(params: GetEvalsByDatasetParams) {
    return this.call<EvalsInfo[]>('getNextEvalsByDatasetId', [params])
  }

  getFreshEvalsByDatasetId(params: GetEvalsByDatasetParams) {
    return this.call<EvalsInfo[]>('getFreshEvalsByDatasetId', [params])
  }

  getAllDatasetEvals(params: Omit<GetEvalsByDatasetParams, 'limit'>) {
    return this.call<EvalsInfo[]>('getAllDatasetEvals', [params])
  }

  getEvalAnnotations(artifactId: string, datasetId: string, evalId: string) {
    return this.call<Annotation[]>('getEvalAnnotations', [artifactId, datasetId, evalId])
  }

  getEvalsDatasetAnnotationsSummary(datasetId: string) {
    return this.call<AnnotationSummary>('getEvalsDatasetAnnotationsSummary', [datasetId])
  }

  getTraces(params: GetTracesParams) {
    return this.call<Trace[]>('getTraces', [params])
  }

  getFreshTraces(params: GetTracesParams) {
    return this.call<Trace[]>('getFreshTraces', [params])
  }

  getAllTraces(params: Omit<GetTracesParams, 'limit'>) {
    return this.call<Trace[]>('getAllTraces', [params])
  }

  resetTracesRequestParams(artifactId?: string) {
    return this.call<void>('resetTracesRequestParams', [artifactId])
  }

  getEvalById(artifactId: string, evalId: string) {
    return this.call<EvalsInfo>('getEvalById', [artifactId, evalId])
  }

  getSpanAnnotations(artifactId: string, traceId: string, spanId: string) {
    return this.call<Annotation[]>('getSpanAnnotations', [artifactId, traceId, spanId])
  }

  getTracesAnnotationSummary(artifactId: string) {
    return this.call<AnnotationSummary>('getTracesAnnotationSummary', [artifactId])
  }

  getTracesColumns(artifactId: string) {
    return this.call<TypedTracesColumns>('getTracesColumns', [artifactId])
  }

  validateEvalsFilter(filters: string[]) {
    return this.call<ValidateResponseItem[]>('validateEvalsFilter', [filters])
  }

  validateTracesFilter(filters: string[]) {
    return this.call<ValidateResponseItem[]>('validateTracesFilter', [filters])
  }
}
