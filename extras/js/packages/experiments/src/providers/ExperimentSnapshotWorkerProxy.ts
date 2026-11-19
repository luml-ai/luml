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
  ReadCallOptions,
} from '../metric-buckets/types'
import type {
  ExperimentSnapshotModelSource,
  SnapshotFailedSource,
  SnapshotOpenFailure,
  SnapshotTransportStats,
} from './ExperimentSnapshotDatabaseProvider'
import { toExperimentReadError } from '../metric-buckets/errors'
import {
  ExperimentSnapshotWorkerTerminatedError,
  isIsolatableSourceFailure,
  isSnapshotSourceExpired,
  isTransientSourceFailure,
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
const TIMED_OUT_MESSAGE = 'Experiment snapshot worker request timed out'

/** A URL lookup that did not answer before the call it serves gave up. */
class SourceLookupTimeoutError extends Error {
  constructor() {
    super(TIMED_OUT_MESSAGE)
    this.name = 'SourceLookupTimeoutError'
  }
}

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
  // Only experiments that read by Range: the others need no URL.
  private rangeSourceUrls = new Map<string, SnapshotSourceRef>()
  private postQueue: Promise<void> | null = null
  private terminated = false
  private readonly statusListeners = new Set<() => void>()

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
    const error = new ExperimentSnapshotWorkerTerminatedError()
    this.pendingRequests.forEach((fail) => fail(error))
  }

  /** Calls `listener` when a call left out an experiment of a comparison, or read it again. */
  onStatusesChanged(listener: () => void): () => void {
    this.statusListeners.add(listener)
    return () => this.statusListeners.delete(listener)
  }

  /** `callerDeadline`: when the caller gives up (epoch ms), if earlier than this proxy does. */
  private request<T>(
    message: Record<string, unknown>,
    signal?: AbortSignal,
    transfer: Transferable[] = [],
    callerDeadline = Infinity,
  ): Promise<T> {
    if (this.terminated) {
      return Promise.reject(new ExperimentSnapshotWorkerTerminatedError())
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
        if (e.data.statusesChanged === true) this.statusListeners.forEach((listener) => listener())
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
        cancel(new Error(TIMED_OUT_MESSAGE))
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

      // The worker skips a call still queued at its deadline: nobody waits for its answer.
      const deadline = Math.min(callerDeadline, Date.now() + this.requestTimeoutMs)
      const posted =
        message.type === 'call' ? { ...message, requestId, deadline } : { ...message, requestId }
      try {
        if (transfer.length) this.worker.postMessage(posted, transfer)
        else this.worker.postMessage(posted)
      } catch (error) {
        cleanup()
        reject(error)
      }
    })
  }

  private call<T>(
    method: string,
    args?: any[],
    signal?: AbortSignal,
    options: ReadCallOptions = {},
  ): Promise<T> {
    const message = { type: 'call', payload: { method, args } }
    const callerDeadline = Date.now() + (options.timeoutMs ?? Infinity)
    if (!this.sourceUrls || !this.rangeSourceUrls.size) {
      return this.inOrder(() => ({ reply: this.request<T>(message, signal, [], callerDeadline) }))
    }
    return this.callWithSourceRenewal<T>(message, signal, callerDeadline)
  }

  /**
   * Posts after every message of the calls made before, so the worker runs calls in the order
   * they were made even when a URL refresh delays one; only posting is ordered, not replies.
   * Posts at once when nothing is queued.
   */
  private inOrder<T>(
    post: () => { reply: Promise<T> } | Promise<{ reply: Promise<T> }>,
  ): Promise<T> {
    let posted: Promise<{ reply: Promise<T> }>
    if (this.postQueue) {
      posted = this.postQueue.then(post)
    } else {
      const started = post()
      if (!(started instanceof Promise)) return started.reply
      posted = started
    }
    const queued = posted.then(
      () => undefined,
      () => undefined,
    )
    this.postQueue = queued
    void queued.then(() => {
      if (this.postQueue === queued) this.postQueue = null
    })
    return posted.then(({ reply }) => reply)
  }

  /**
   * Range reads run synchronously in the worker, so an expired URL or token fails the running
   * request. Each model's source is renewed at most once per request and the request retried;
   * sources of several models can expire together, so one request may renew each of them. A
   * second failure of the same model surfaces. A renewal that hands back the source that just
   * failed (it is too young to renew) gets one retry with it after a transient failure, and
   * surfaces any other failure at once. In a read that spans several experiments, a failure
   * that surfaces is instead left out: the call is retried without reading that experiment,
   * and the others answer.
   */
  private async callWithSourceRenewal<T>(
    message: { type: string; payload: unknown },
    signal: AbortSignal | undefined,
    callerDeadline: number,
  ): Promise<T> {
    const renewed = new Set<string>()
    const failedSources: SnapshotFailedSource[] = []
    let usedUrls = new Map(this.rangeSourceUrls)
    let first = true
    for (;;) {
      const refresh = first
      first = false
      const post = async () => {
        if (refresh) {
          const deadline = Math.min(callerDeadline, Date.now() + this.requestTimeoutMs)
          await this.sendAgedSourceUrls(deadline, signal)
        }
        usedUrls = new Map(this.rangeSourceUrls)
        const renewableSources = [...usedUrls.keys()].filter((modelId) => !renewed.has(modelId))
        const context = { renewableSources, failedSources: [...failedSources] }
        return { reply: this.request<T>({ ...message, context }, signal, [], callerDeadline) }
      }
      try {
        return await this.inOrder(post)
      } catch (error) {
        const leaveOut = () => {
          if (!isIsolatableSourceFailure(error)) return false
          const { modelId } = error as SnapshotSourceExpiredError
          if (failedSources.some((failed) => failed.modelId === modelId)) return false
          failedSources.push({ modelId, error: toExperimentReadError(error) })
          return true
        }
        if (!this.canRenew(error) || renewed.has(error.modelId)) {
          if (leaveOut()) continue
          throw error
        }
        renewed.add(error.modelId)
        const failed = usedUrls.get(error.modelId)!
        let source: SnapshotSourceRef
        try {
          source = await this.sourceUrls!.renew(error.modelId, failed)
        } catch (renewError) {
          if (isAbortError(renewError) || !leaveOut()) throw renewError
          continue
        }
        if (sameSourceLocation(source, failed)) {
          if (isTransientSourceFailure(error) || leaveOut()) continue
          throw error
        }
        const rangeBacked = await this.sendSourceUrl(error.modelId, source, signal)
        if (rangeBacked === false) this.rangeSourceUrls.delete(error.modelId)
        else this.rangeSourceUrls.set(error.modelId, source)
      }
    }
  }

  /**
   * Opens every experiment; one that cannot open is reported by its status and the others
   * work. An experiment whose source failed at open is renewed once and only it is opened
   * again, so nothing already open is probed or downloaded twice. When the renewal hands back
   * the source that failed, only a transient failure is opened again, once, with it.
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
    const stillFailed = new Set(failures.map(({ modelId }) => modelId))
    await Promise.all(
      failures
        .filter(({ modelId, error }) => this.canRenewOpen(modelId, error.code))
        .map(async ({ modelId, transient }) => {
          if (await this.reopen(modelId, transient === true, signal)) stillFailed.delete(modelId)
        }),
    )
    // An experiment that did not open reads nothing, so its URL is never renewed or sent.
    for (const modelId of stillFailed) this.rangeSourceUrls.delete(modelId)
  }

  private canRenewOpen(modelId: string, code: string): boolean {
    return (
      this.sourceUrls !== null &&
      code === SNAPSHOT_SOURCE_EXPIRED &&
      this.rangeSourceUrls.has(modelId)
    )
  }

  /**
   * A renewal or reopen that fails, or a renewal that hands back the source of a failure that
   * was not transient, leaves the experiment failed with the error the worker recorded at open,
   * so one experiment never fails the whole init. True when the experiment opened.
   */
  private async reopen(
    modelId: string,
    transient: boolean,
    signal?: AbortSignal,
  ): Promise<boolean> {
    const failed = this.rangeSourceUrls.get(modelId)
    if (!this.sourceUrls || failed === undefined) return false
    try {
      const source = await this.sourceUrls.renew(modelId, failed)
      signal?.throwIfAborted()
      if (sameSourceLocation(source, failed) && !transient) return false
      const location = toSourceLocation(source)
      this.rangeSourceUrls.set(modelId, source)
      const failures = await this.request<SnapshotOpenFailure[]>(
        { type: 'reopen', payload: { modelId, source: location } },
        signal,
      )
      return Array.isArray(failures) && !failures.some((item) => item.modelId === modelId)
    } catch (error) {
      if (signal?.aborted || isAbortError(error)) throw error
      return false
    }
  }

  private canRenew(error: unknown): error is SnapshotSourceExpiredError {
    return (
      this.sourceUrls !== null &&
      isSnapshotSourceExpired(error) &&
      this.rangeSourceUrls.has(error.modelId)
    )
  }

  /**
   * Posts the URLs that aged since they were sent, without waiting for the answers: the call
   * posted next reaches the worker after them. A URL lookup that fails keeps the URL sent
   * before; a read that needs it then fails for that experiment only, and is renewed. One
   * still unanswered at `deadline`, or when `signal` aborts, fails the call, so that the
   * calls queued behind it are posted.
   */
  private async sendAgedSourceUrls(deadline: number, signal?: AbortSignal) {
    if (!this.sourceUrls) return
    for (const [modelId, sent] of this.rangeSourceUrls) {
      let current: SnapshotSourceRef
      try {
        current = await this.lookUpSourceUrl(modelId, deadline, signal)
      } catch (error) {
        if (error instanceof SourceLookupTimeoutError || isAbortError(error)) throw error
        continue
      }
      if (sameSourceLocation(current, sent) || this.rangeSourceUrls.get(modelId) !== sent) continue
      this.rangeSourceUrls.set(modelId, current)
      this.sendSourceUrl(modelId, current, signal).then(
        (rangeBacked) => {
          if (rangeBacked === false && this.rangeSourceUrls.get(modelId) === current) {
            this.rangeSourceUrls.delete(modelId)
          }
        },
        () => {
          if (this.rangeSourceUrls.get(modelId) === current) this.rangeSourceUrls.set(modelId, sent)
        },
      )
    }
  }

  private lookUpSourceUrl(
    modelId: string,
    deadline: number,
    signal?: AbortSignal,
  ): Promise<SnapshotSourceRef> {
    const lookup = this.sourceUrls!.get(modelId)
    return new Promise((resolve, reject) => {
      const settle = (done: () => void) => {
        clearTimeout(timer)
        signal?.removeEventListener('abort', onAbort)
        done()
      }
      const onAbort = () => settle(() => reject(new DOMException('Aborted', 'AbortError')))
      const timer = setTimeout(
        () => settle(() => reject(new SourceLookupTimeoutError())),
        Math.max(0, deadline - Date.now()),
      )
      if (signal?.aborted) {
        onAbort()
        return
      }
      signal?.addEventListener('abort', onAbort)
      lookup.then(
        (source) => settle(() => resolve(source)),
        (error: unknown) => settle(() => reject(error)),
      )
    })
  }

  /** False when the experiment does not read by Range (it was loaded in full). */
  private sendSourceUrl(
    modelId: string,
    source: SnapshotSourceRef,
    signal?: AbortSignal,
  ): Promise<boolean | undefined> {
    return this.request<boolean | undefined>(
      { type: 'call', payload: { method: 'setSourceUrl', args: [modelId, source] } },
      signal,
    )
  }

  getStaticParamsList(signal?: AbortSignal) {
    return this.call<ExperimentSnapshotStaticParams[]>('getStaticParamsList', undefined, signal)
  }

  getExperimentStatuses(signal?: AbortSignal, options?: ReadCallOptions) {
    return this.call<ExperimentSnapshotStatus[]>(
      'getExperimentStatuses',
      undefined,
      signal,
      options,
    )
  }

  getMetricCatalogs(
    request?: MetricCatalogsRequest,
    signal?: AbortSignal,
    options?: ReadCallOptions,
  ) {
    return this.call<ExperimentResult<ExperimentMetricCatalog>[]>(
      'getMetricCatalogs',
      [request],
      signal,
      options,
    )
  }

  getMetricBuckets(request: MetricBucketsRequest, signal?: AbortSignal, options?: ReadCallOptions) {
    return this.call<ExperimentResult<MetricBucketsResponse>[]>(
      'getMetricBuckets',
      [request],
      signal,
      options,
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
