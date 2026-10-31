import type { Annotation, AnnotationSummary } from '@/components/annotations/annotations.interface'
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
  GetBatchExperimentEvalsParams,
} from '../interfaces/interfaces'
import type { Trace } from './ExperimentSnapshotApiProvider.interface'

export class ExperimentSnapshotWorkerProxy implements ExperimentSnapshotProvider {
  constructor(private worker: Worker) {}

  private request<T>(message: Record<string, unknown>, signal?: AbortSignal): Promise<T> {
    const requestId = crypto.randomUUID()

    return new Promise((resolve, reject) => {
      const handler = (e: MessageEvent) => {
        if (e.data?.requestId !== requestId) return
        if (e.data.type !== 'error' && e.data.type !== 'result') return
        cleanup()
        if (e.data.type === 'error') {
          reject(e.data.error)
        } else {
          resolve(e.data.data)
        }
      }

      const onError = (event: ErrorEvent) => {
        cleanup()
        reject(new Error(event.message || 'Experiment snapshot worker failed'))
      }

      const onMessageError = () => {
        cleanup()
        reject(new Error('Experiment snapshot worker response could not be deserialized'))
      }

      const cancel = (error: Error) => {
        cleanup()
        reject(error)
        try {
          this.worker.postMessage({ type: 'cancel', requestId })
        } catch {
          // the worker may already be unavailable
        }
      }

      const onAbort = () => cancel(new DOMException('Aborted', 'AbortError'))
      const timeout = setTimeout(() => {
        cancel(new Error('Experiment snapshot worker request timed out'))
      }, 60_000)

      const cleanup = () => {
        clearTimeout(timeout)
        this.worker.removeEventListener('message', handler)
        this.worker.removeEventListener('error', onError)
        this.worker.removeEventListener('messageerror', onMessageError)
        signal?.removeEventListener('abort', onAbort)
      }

      this.worker.addEventListener('message', handler)
      this.worker.addEventListener('error', onError)
      this.worker.addEventListener('messageerror', onMessageError)

      if (signal) {
        if (signal.aborted) {
          onAbort()
          return
        }
        signal.addEventListener('abort', onAbort)
      }

      try {
        this.worker.postMessage({ ...message, requestId })
      } catch (error) {
        cleanup()
        reject(error)
      }
    })
  }

  private call<T>(method: string, args?: any[], signal?: AbortSignal): Promise<T> {
    return this.request<T>({ type: 'call', payload: { method, args } }, signal)
  }

  init(data: any) {
    return this.request<void>({ type: 'init', payload: data })
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

  getDatasetAverageScores(datasetId: string, search?: string, filters?: string[]) {
    return this.call<ModelScores[]>('getDatasetAverageScores', [datasetId, search, filters])
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

  getBatchExperimentEvals(params: GetBatchExperimentEvalsParams) {
    return this.call<{ items: EvalsInfo[]; cursor: string | null }>('getBatchExperimentEvals', [
      params,
    ])
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
