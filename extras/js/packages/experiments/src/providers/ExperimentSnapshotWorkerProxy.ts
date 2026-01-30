import type {
  EvalsListType,
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  SpansListType,
  SpansParams,
  TraceSpan,
} from '../interfaces/interfaces'

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

  init(data: any[]) {
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

  getEvalsList(signal?: AbortSignal) {
    return this.call<EvalsListType>('getEvalsList', undefined, signal)
  }

  buildSpanTree(spans: Omit<TraceSpan, 'children'>[]) {
    return this.call<TraceSpan[]>('buildSpanTree', [spans])
  }

  getTraceId(args: SpansParams) {
    return this.call<string>('getTraceId', [args])
  }

  getUniqueTraceIds(modelId: string) {
    return this.call<string[]>('getUniqueTraceIds', [modelId])
  }

  getTraceSpans(modelId: string, traceId: string) {
    return this.call<SpansListType>('getTraceSpans', [modelId, traceId])
  }
}
