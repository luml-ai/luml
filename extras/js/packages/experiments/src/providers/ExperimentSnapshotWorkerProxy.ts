import type { Annotation, AnnotationSummary } from '@/components/annotations/annotations.interface'
import type {
  EvalsInfo,
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  ExperimentSnapshotStaticParams,
  GetEvalsByDatasetParams,
  GetTracesParams,
  ModelScores,
  SpanPayload,
  SpansListType,
  TypedEvalsColumns,
  SpansParams,
  TraceSpan,
  TypedTracesColumns,
  ValidateResponseItem,
  GetBatchExperimentEvalsParams,
} from '../interfaces/interfaces'
import type { Trace } from './ExperimentSnapshotApiProvider.interface'
import type {
  ExperimentMetricCatalog,
  ExperimentResult,
  ExperimentSnapshotStatus,
  MetricBucketsRequest,
  MetricBucketsResponse,
  MetricCatalogsRequest,
} from '../metric-buckets/types'
import type {
  ExperimentSnapshotModelSource,
  SnapshotOpenFailure,
  SnapshotTransportStats,
} from './ExperimentSnapshotDatabaseProvider'
import {
  isSnapshotSourceExpired,
  redactSecrets,
  SNAPSHOT_SOURCE_EXPIRED,
  snapshotErrorFields,
  snapshotErrorFromFields,
  type SnapshotSourceExpiredError,
} from './snapshot-source/errors'
import { rangeSourceLocation, type RangeSnapshotSource } from './snapshot-source/openRawSnapshot'
import {
  sameSourceLocation,
  toSourceLocation,
  type SnapshotSourceRef,
} from './snapshot-source/sourceLocation'

const DEFAULT_REQUEST_TIMEOUT_MS = 60_000

/**
 * Owns the URLs (or URLs with headers, such as a bearer token) of range-backed snapshots on
 * the main thread.
 */
export interface SnapshotSourceUrlProvider {
  /** The current URL or location; renews it when it is too old. */
  get(modelId: string): Promise<SnapshotSourceRef>
  /** A request with `failed`, as this provider returned it, failed: returns a renewed one. */
  renew(modelId: string, failed: SnapshotSourceRef): Promise<SnapshotSourceRef>
}

export interface ExperimentSnapshotWorkerProxyOptions {
  requestTimeoutMs?: number
  sourceUrls?: SnapshotSourceUrlProvider
}

function snapshotBuffers(modelsInfo: ExperimentSnapshotModelSource[]): ArrayBuffer[] {
  return modelsInfo.flatMap((info) => {
    if ('error' in info) return []
    if (!('source' in info)) return [info.buffer]
    return info.source.kind === 'range' ? [] : [info.source.buffer]
  })
}

function workerError(data: { error: unknown }): Error {
  const message = redactSecrets(String(data.error))
  const fields = snapshotErrorFields(data)
  return fields ? snapshotErrorFromFields(fields, message) : new Error(message)
}

function isAbortError(error: unknown): boolean {
  return (error as { name?: unknown } | null)?.name === 'AbortError'
}

/** A source without headers is handed to the URL provider as the bare URL it issued. */
function sourceRefOf(source: RangeSnapshotSource): SnapshotSourceRef {
  return source.headers || source.credentials ? rangeSourceLocation(source) : source.url
}

export class ExperimentSnapshotWorkerProxy implements ExperimentSnapshotProvider {
  private readonly requestTimeoutMs: number
  private readonly sourceUrls: SnapshotSourceUrlProvider | null
  private readonly pendingRequests = new Set<(error: Error) => void>()
  private rangeSourceUrls = new Map<string, SnapshotSourceRef>()
  private terminated = false

  constructor(
    private worker: Worker,
    options: ExperimentSnapshotWorkerProxyOptions = {},
  ) {
    this.requestTimeoutMs = options.requestTimeoutMs ?? DEFAULT_REQUEST_TIMEOUT_MS
    this.sourceUrls = options.sourceUrls ?? null
  }

  terminate() {
    if (this.terminated) return
    this.terminated = true
    this.worker.terminate()
    const error = new Error('Experiment snapshot worker was terminated')
    this.pendingRequests.forEach((fail) => fail(error))
  }

  private request<T>(
    message: Record<string, unknown>,
    signal?: AbortSignal,
    transfer: Transferable[] = [],
  ): Promise<T> {
    if (this.terminated) {
      return Promise.reject(new Error('Experiment snapshot worker was terminated'))
    }
    const requestId = crypto.randomUUID()

    return new Promise((resolve, reject) => {
      const handler = (e: MessageEvent) => {
        if (e.data?.requestId !== requestId) return
        if (e.data.type !== 'error' && e.data.type !== 'result') return
        cleanup()
        if (e.data.type === 'error') {
          reject(workerError(e.data))
        } else {
          resolve(e.data.data)
        }
      }

      const onError = (event: ErrorEvent) => {
        cleanup()
        const message = event.message ? redactSecrets(event.message) : ''
        reject(new Error(message || 'Experiment snapshot worker failed'))
      }

      const fail = (error: Error) => {
        cleanup()
        reject(error)
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
          return
        }
      }

      const onAbort = () => cancel(new DOMException('Aborted', 'AbortError'))
      const timeout = setTimeout(() => {
        cancel(new Error('Experiment snapshot worker request timed out'))
      }, this.requestTimeoutMs)

      const cleanup = () => {
        clearTimeout(timeout)
        this.worker.removeEventListener('message', handler)
        this.worker.removeEventListener('error', onError)
        this.worker.removeEventListener('messageerror', onMessageError)
        signal?.removeEventListener('abort', onAbort)
        this.pendingRequests.delete(fail)
      }

      this.pendingRequests.add(fail)
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
        if (transfer.length) this.worker.postMessage({ ...message, requestId }, transfer)
        else this.worker.postMessage({ ...message, requestId })
      } catch (error) {
        cleanup()
        reject(error)
      }
    })
  }

  private call<T>(method: string, args?: any[], signal?: AbortSignal): Promise<T> {
    const message = { type: 'call', payload: { method, args } }
    if (!this.sourceUrls || !this.rangeSourceUrls.size) return this.request<T>(message, signal)
    return this.callWithSourceRenewal<T>(message, signal)
  }

  private async callWithSourceRenewal<T>(
    message: Record<string, unknown>,
    signal?: AbortSignal,
  ): Promise<T> {
    await this.sendAgedSourceUrls(signal)
    return this.withSourceRenewal(
      () => this.request<T>(message, signal),
      (modelId, source) => this.sendSourceUrl(modelId, source, signal),
    )
  }

  /**
   * Range reads run synchronously in the worker, so an expired URL or token fails the running
   * request. Each model's source is renewed at most once per request and the request retried;
   * sources of several models can expire together, so one request may renew each of them. A
   * second failure of the same model surfaces, and so does a renewal that hands back the source
   * that just failed.
   */
  private async withSourceRenewal<T>(
    attempt: () => Promise<T>,
    applyRenewedUrl: (modelId: string, source: SnapshotSourceRef) => Promise<void>,
  ): Promise<T> {
    const renewed = new Set<string>()
    for (;;) {
      const usedUrls = new Map(this.rangeSourceUrls)
      try {
        return await attempt()
      } catch (error) {
        if (!this.canRenew(error) || renewed.has(error.modelId)) throw error
        renewed.add(error.modelId)
        const failed = usedUrls.get(error.modelId)!
        const source = await this.sourceUrls!.renew(error.modelId, failed)
        if (sameSourceLocation(source, failed)) throw error
        await applyRenewedUrl(error.modelId, source)
        this.rangeSourceUrls.set(error.modelId, source)
      }
    }
  }

  /**
   * Opens every experiment; one that cannot open is reported by its status and the others
   * work. An experiment whose source failed at open is renewed once and only it is opened
   * again, so nothing already open is probed or downloaded twice.
   */
  async init(modelsInfo: ExperimentSnapshotModelSource[], signal?: AbortSignal): Promise<void> {
    this.rangeSourceUrls = new Map(
      modelsInfo.flatMap((info) =>
        'source' in info && info.source.kind === 'range'
          ? [[info.modelId, sourceRefOf(info.source)] as const]
          : [],
      ),
    )
    const answer = await this.request<SnapshotOpenFailure[] | true>(
      { type: 'init', payload: modelsInfo },
      signal,
      snapshotBuffers(modelsInfo),
    )
    const failures = Array.isArray(answer) ? answer : []
    await Promise.all(
      failures
        .filter(({ modelId, error }) => this.canRenewOpen(modelId, error.code))
        .map(({ modelId }) => this.reopen(modelId, signal)),
    )
  }

  private canRenewOpen(modelId: string, code: string): boolean {
    return (
      this.sourceUrls !== null &&
      code === SNAPSHOT_SOURCE_EXPIRED &&
      this.rangeSourceUrls.has(modelId)
    )
  }

  /**
   * A renewal or reopen that fails, or a renewal that hands back the failed source, leaves the
   * experiment failed with the error the worker recorded at open, so one experiment never fails
   * the whole init.
   */
  private async reopen(modelId: string, signal?: AbortSignal): Promise<void> {
    const failed = this.rangeSourceUrls.get(modelId)
    if (!this.sourceUrls || failed === undefined) return
    try {
      const source = await this.sourceUrls.renew(modelId, failed)
      signal?.throwIfAborted()
      if (sameSourceLocation(source, failed)) return
      const location = toSourceLocation(source)
      this.rangeSourceUrls.set(modelId, source)
      await this.request<SnapshotOpenFailure[]>(
        { type: 'reopen', payload: { modelId, source: location } },
        signal,
      )
    } catch (error) {
      if (signal?.aborted || isAbortError(error)) throw error
    }
  }

  private canRenew(error: unknown): error is SnapshotSourceExpiredError {
    return (
      this.sourceUrls !== null &&
      isSnapshotSourceExpired(error) &&
      this.rangeSourceUrls.has(error.modelId)
    )
  }

  private async sendAgedSourceUrls(signal?: AbortSignal) {
    if (!this.sourceUrls) return
    for (const [modelId, sent] of this.rangeSourceUrls) {
      const current = await this.sourceUrls.get(modelId)
      if (sameSourceLocation(current, sent) || this.rangeSourceUrls.get(modelId) !== sent) continue
      this.rangeSourceUrls.set(modelId, current)
      await this.sendSourceUrl(modelId, current, signal)
    }
  }

  private sendSourceUrl(modelId: string, source: SnapshotSourceRef, signal?: AbortSignal) {
    return this.request<void>(
      { type: 'call', payload: { method: 'setSourceUrl', args: [modelId, source] } },
      signal,
    )
  }

  getStaticParamsList(signal?: AbortSignal) {
    return this.call<ExperimentSnapshotStaticParams[]>('getStaticParamsList', undefined, signal)
  }

  getExperimentStatuses(signal?: AbortSignal) {
    return this.call<ExperimentSnapshotStatus[]>('getExperimentStatuses', undefined, signal)
  }

  getMetricCatalogs(request?: MetricCatalogsRequest, signal?: AbortSignal) {
    return this.call<ExperimentResult<ExperimentMetricCatalog>[]>(
      'getMetricCatalogs',
      [request],
      signal,
    )
  }

  getMetricBuckets(request: MetricBucketsRequest, signal?: AbortSignal) {
    return this.call<ExperimentResult<MetricBucketsResponse>[]>(
      'getMetricBuckets',
      [request],
      signal,
    )
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

  getSpanPayload(modelId: string, traceId: string, spanId: string) {
    return this.call<SpanPayload>('getSpanPayload', [modelId, traceId, spanId])
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

  getTransportStats(signal?: AbortSignal) {
    return this.call<SnapshotTransportStats[]>('getTransportStats', undefined, signal)
  }

  validateTracesFilter(filters: string[]) {
    return this.call<ValidateResponseItem[]>('validateTracesFilter', [filters])
  }
}
