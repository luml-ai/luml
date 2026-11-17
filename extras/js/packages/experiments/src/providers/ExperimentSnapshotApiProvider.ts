import type {
  EvalsInfo,
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  GetEvalsByDatasetParams,
  GetTracesParams,
  SpansListType,
  SpansParams,
  TraceSpan,
  TypedEvalsColumns,
  TypedTracesColumns,
  ValidateResponseItem,
} from '@/interfaces/interfaces'
import type {
  ArtifactInfo,
  ApiServiceInterface,
  ExperimentMetricHistory,
  SpanFromApi,
  GetBatchExperimentsEvalsParams,
  MetricBucketsWire,
  MetricBucketWire,
  MetricCatalogWire,
  WireNumber,
} from './ExperimentSnapshotApiProvider.interface'
import {
  INVALID_LEVEL,
  NEEDS_NEWER_READER,
  READ_FAILED,
  TOO_MANY_BUCKETS,
  type ExperimentMetricCatalog,
  type ExperimentReadError,
  type ExperimentResult,
  type ExperimentSnapshotStatus,
  type MetricBucketsRequest,
  type MetricBucketsResponse,
  type MetricCatalogsRequest,
} from '@/metric-buckets/types'
import { toExperimentReadError } from '@/metric-buckets/errors'
import { redactSecrets } from './snapshot-source/errors'
import { NEWEST_KNOWN_REVISION } from './ExperimentSnapshotTraits'
import type {
  AddAnnotationPayload,
  UpdateAnnotationPayload,
} from '@/components/annotations/annotations.interface'

function decodeWireNumber(value: WireNumber): number | null {
  if (value === 'Infinity') return Infinity
  if (value === '-Infinity') return -Infinity
  if (value === null || typeof value === 'number') return value
  throw new TypeError(`Unexpected number encoding ${JSON.stringify(value)}`)
}

function decodeSum(value: number | null): number | null {
  if (value === null || typeof value === 'number') return value
  throw new TypeError(`Unexpected bucket sum ${JSON.stringify(value)}`)
}

function decodeCatalog(wire: MetricCatalogWire): ExperimentMetricCatalog {
  return {
    revision: wire.revision,
    bucket_min_level: wire.bucket_min_level,
    bucket_max_level: wire.bucket_max_level,
    skipped_rows: wire.skipped_rows,
    metrics: wire.metrics.map((metric) => ({
      ...metric,
      min: decodeWireNumber(metric.min),
      max: decodeWireNumber(metric.max),
    })),
  }
}

function decodeBucket([
  bucket,
  firstStep,
  lastStep,
  count,
  finiteCount,
  min,
  max,
  sum,
]: MetricBucketWire) {
  return {
    bucket,
    first_step: firstStep,
    last_step: lastStep,
    count,
    finite_count: finiteCount,
    min: decodeWireNumber(min),
    max: decodeWireNumber(max),
    sum: decodeSum(sum),
  }
}

function decodeBuckets(wire: MetricBucketsWire): MetricBucketsResponse {
  return {
    level: wire.level,
    series: wire.series.map((series) => ({ ...series, buckets: series.buckets.map(decodeBucket) })),
  }
}

const CODES_BY_STATUS: Record<number, ExperimentReadError['code'][]> = {
  409: [NEEDS_NEWER_READER],
  422: [INVALID_LEVEL, TOO_MANY_BUCKETS],
}

/**
 * The Flow API answers 409 and 422 with `{"detail": {"code", "message"}}`; those codes become
 * the typed errors the database provider raises, anything else (404 included) `read-failed`.
 * The error is read the way axios rejects: `{response: {status, data}}`.
 */
function apiReadError(error: unknown): ExperimentReadError {
  const response = (error as { response?: { status?: unknown; data?: unknown } } | null)?.response
  const detail = (response?.data as { detail?: { code?: unknown; message?: unknown } } | null)
    ?.detail
  const known = typeof response?.status === 'number' ? CODES_BY_STATUS[response.status] : undefined
  const code = known?.find((candidate) => candidate === detail?.code)
  if (code) {
    const message = redactSecrets(
      typeof detail?.message === 'string' ? detail.message : String(detail?.code),
    )
    return { code, message }
  }
  const fallback = toExperimentReadError(error)
  return response ? { code: READ_FAILED, message: fallback.message } : fallback
}

export class ExperimentSnapshotApiProvider implements ExperimentSnapshotProvider {
  private _artifacts: ArtifactInfo[] | null = null
  private catalogResults = new Map<string, ExperimentResult<ExperimentMetricCatalog>>()
  private _datasetsCursors: Record<string, Array<string | null>> = {}
  private _tracesCursors: Record<string, Array<string | null>> = {}

  get artifacts() {
    if (!this._artifacts) throw new Error('Experiments not initialized')
    return this._artifacts
  }

  set artifacts(value: ArtifactInfo[]) {
    this._artifacts = value
  }

  constructor(private readonly apiService: ApiServiceInterface) {}

  async init(data: { artifacts: ArtifactInfo[] }) {
    this._artifacts = data.artifacts
    this.catalogResults = new Map()
  }

  async getExperimentStatuses(): Promise<ExperimentSnapshotStatus[]> {
    return this.artifacts.map(({ id }) => {
      const catalog = this.catalogResults.get(id)
      const revision = catalog?.ok ? catalog.value.revision : null
      return {
        modelId: id,
        revision,
        transport: 'api',
        transportFallback: null,
        unknownNewerRevision: revision !== null && revision > NEWEST_KNOWN_REVISION,
        skippedMetricRows: catalog?.ok ? catalog.value.skipped_rows : null,
        error: catalog && !catalog.ok ? catalog.error : null,
      }
    })
  }

  /** One `GET metric-catalog` per experiment, always from the server (live runs grow). */
  async getMetricCatalogs(request: MetricCatalogsRequest = {}, signal?: AbortSignal) {
    const fetchCatalog = this.apiService.getExperimentMetricCatalog?.bind(this.apiService)
    const artifacts = request.modelIds
      ? this.artifacts.filter(({ id }) => request.modelIds?.includes(id))
      : this.artifacts
    const results = await Promise.all(
      artifacts.map(({ id }) =>
        this.apiResult(id, signal, async () => {
          if (!fetchCatalog) throw new Error('The API does not serve metric catalogs')
          return decodeCatalog(await fetchCatalog(id, signal))
        }),
      ),
    )
    for (const result of results) this.catalogResults.set(result.modelId, result)
    return results
  }

  /** One `POST metric-buckets` per experiment, all keys in its body. */
  async getMetricBuckets(request: MetricBucketsRequest, signal?: AbortSignal) {
    const fetchBuckets = this.apiService.getExperimentMetricBuckets?.bind(this.apiService)
    const body = {
      keys: request.keys,
      start_step: request.start_step ?? null,
      end_step: request.end_step ?? null,
      level: request.level,
    }
    const artifacts = request.modelIds
      ? this.artifacts.filter(({ id }) => request.modelIds?.includes(id))
      : this.artifacts
    return Promise.all(
      artifacts.map(({ id }) =>
        this.apiResult(id, signal, async () => {
          if (!fetchBuckets) throw new Error('The API does not serve metric buckets')
          return decodeBuckets(await fetchBuckets(id, body, signal))
        }),
      ),
    )
  }

  /** Per-experiment errors; an abort rejects the whole call. */
  private async apiResult<T>(
    modelId: string,
    signal: AbortSignal | undefined,
    read: () => Promise<T>,
  ): Promise<ExperimentResult<T>> {
    try {
      return { modelId, ok: true, value: await read() }
    } catch (error) {
      if (signal?.aborted) throw error
      return { modelId, ok: false, error: apiReadError(error) }
    }
  }

  async getDynamicMetricsNames() {
    return this.artifacts.map((artifact) => artifact.dynamicMetrics).flat()
  }

  async getDynamicMetricData(metricName: string, signal?: AbortSignal) {
    const promises = this.artifacts.map(async (artifact) => {
      const data = await this.apiService.getExperimentMetricHistory(
        artifact.id,
        metricName,
        undefined,
        signal,
      )
      return this.prepareMetricData(data)
    })
    return Promise.all(promises)
  }

  async getStaticParamsList() {
    return this.artifacts.map((artifact) => {
      return { ...artifact.staticParams, modelId: artifact.id }
    })
  }

  async getTraceSpans(modelId: string, traceId: string): Promise<SpansListType> {
    const { spans, trace_id } = await this.apiService.getTraceDetails(modelId, traceId)
    const spansList = spans.map((span) => this.prepareSpan(span, trace_id))
    return spansList
  }

  async buildSpanTree(spans: Omit<TraceSpan, 'children'>[]): Promise<TraceSpan[]> {
    const spanMap: Record<string, TraceSpan> = {}
    spans.forEach((span) => {
      spanMap[span.span_id] = { ...span, children: [] }
    })
    const roots: TraceSpan[] = []
    for (const span of Object.values(spanMap)) {
      if (span.parent_span_id) {
        const parent = spanMap[span.parent_span_id]
        if (parent) {
          parent.children!.push(span)
        } else {
          roots.push(span)
        }
      } else {
        roots.push(span)
      }
    }
    return this.sortSpans(roots)
  }

  async getTraceId(params: SpansParams) {
    const evaluation = await this.apiService.getEvalById(params.modelId, params.evalId)
    return evaluation.dataset_id === params.datasetId ? (evaluation.trace_ids[0] ?? null) : null
  }

  async getEvalsColumns(datasetId: string): Promise<TypedEvalsColumns> {
    const responses = this.artifacts.map(async (artifact) => {
      return this.apiService.getTypedEvalsColumns(artifact.id, datasetId)
    })
    const columnsByArtifact = await Promise.all(responses)
    const result = columnsByArtifact.reduce(
      (acc, columns) => {
        const keys: (keyof TypedEvalsColumns)[] = [
          'inputs',
          'outputs',
          'refs',
          'scores',
          'metadata',
          'annotations_feedback',
          'annotations_expectations',
        ]
        keys.forEach((key) => {
          columns[key].forEach((item) => {
            const columnExists = acc[key].find((column) => column.name === item.name)
            if (!columnExists) {
              acc[key].push(item)
            }
          })
        })
        return acc
      },
      {
        inputs: [],
        outputs: [],
        refs: [],
        scores: [],
        metadata: [],
        annotations_feedback: [],
        annotations_expectations: [],
      },
    )
    return result
  }

  async getUniqueDatasetsIds(): Promise<string[]> {
    const responses = this.artifacts.map(async (artifact) =>
      this.apiService.getExperimentUniqueDatasetsIds(artifact.id),
    )
    const datasetsIds = await Promise.all(responses)
    const uniqueDatasetsIds = new Set(datasetsIds.flat())
    return Array.from(uniqueDatasetsIds)
  }

  async getNextEvalsByDatasetId(params: GetEvalsByDatasetParams): Promise<EvalsInfo[]> {
    if (this.artifacts.length > 1) return this.getNextBatchEvalsByDatasetId(params)
    const responses = this.artifacts.map(async (artifact) => {
      const cursors = this._datasetsCursors[params.dataset_id] || []
      const currentCursor = cursors[cursors.length - 1]
      if (currentCursor === null) return []
      const { items, cursor: newCursor } = await this.apiService.getExperimentEvals({
        ...params,
        experiment_id: artifact.id,
        cursor: currentCursor,
      })
      this._datasetsCursors[params.dataset_id] = [...cursors, newCursor]
      return items.map((item) => ({ ...item, modelId: artifact.id }))
    })
    const evalsByArtifact = await Promise.all(responses)
    return evalsByArtifact.flat()
  }

  async getFreshEvalsByDatasetId(params: GetEvalsByDatasetParams): Promise<EvalsInfo[]> {
    if (this.artifacts.length > 1) return this.getFreshBatchEvalsByDatasetId(params)
    const responses = this.artifacts.map(async (artifact) => {
      const cursors = this._datasetsCursors[params.dataset_id] || []
      const cursorsList = [null, ...cursors]
      cursorsList.pop()
      const promises = cursorsList.map(async (cursor) => {
        const { items } = await this.apiService.getExperimentEvals({
          ...params,
          experiment_id: artifact.id,
          cursor,
        })
        return items.map((item) => ({ ...item, modelId: artifact.id }))
      })
      const evalsByCursor = await Promise.all(promises)
      return evalsByCursor.flat()
    })
    const evalsByArtifact = await Promise.all(responses)
    return evalsByArtifact.flat()
  }

  private async getNextBatchEvalsByDatasetId(
    params: GetEvalsByDatasetParams,
  ): Promise<EvalsInfo[]> {
    const cursors = this._datasetsCursors[params.dataset_id] || []
    const currentCursor = cursors[cursors.length - 1]
    if (currentCursor === null) return []
    const { items, cursor: newCursor } = await this.getBatchExperimentEvals({
      experiment_ids: this.artifacts.map((artifact) => artifact.id),
      limit: params.limit,
      cursor: currentCursor,
      dataset_id: params.dataset_id,
      search: params.search,
      filters: params.filters,
    })
    this._datasetsCursors[params.dataset_id] = [...cursors, newCursor]
    return items
  }

  private async getFreshBatchEvalsByDatasetId(
    params: GetEvalsByDatasetParams,
  ): Promise<EvalsInfo[]> {
    const cursors = this._datasetsCursors[params.dataset_id] || []
    const cursorsList: Array<string | null> = [null, ...cursors]
    cursorsList.pop()
    const promises = cursorsList.map(async (cursor) => {
      const { items } = await this.getBatchExperimentEvals({
        experiment_ids: this.artifacts.map((artifact) => artifact.id),
        limit: params.limit,
        cursor,
        dataset_id: params.dataset_id,
        search: params.search,
        filters: params.filters,
      })
      return items
    })
    const evalsByCursor = await Promise.all(promises)
    return evalsByCursor.flat()
  }

  async getAllDatasetEvals(params: Omit<GetEvalsByDatasetParams, 'limit'>): Promise<EvalsInfo[]> {
    const responses = this.artifacts.map(async (artifact) => {
      const evals = await this.apiService.getAllExperimentEvals({
        ...params,
        experiment_id: artifact.id,
      })
      return evals.map((item) => ({ ...item, modelId: artifact.id }))
    })
    const evalsByArtifact = await Promise.all(responses)
    return evalsByArtifact.flat()
  }

  async createEvalAnnotation(
    artifactId: string,
    datasetId: string,
    evalId: string,
    data: AddAnnotationPayload,
  ) {
    return this.apiService.createEvalAnnotation(artifactId, datasetId, evalId, data)
  }

  async updateEvalAnnotation(
    artifactId: string,
    annotationId: string,
    data: UpdateAnnotationPayload,
  ) {
    return this.apiService.updateEvalAnnotation(artifactId, annotationId, data)
  }

  async getEvalAnnotations(artifactId: string, datasetId: string, evalId: string) {
    return this.apiService.getEvalAnnotations(artifactId, datasetId, evalId)
  }

  async deleteEvalAnnotation(artifactId: string, annotationId: string) {
    return this.apiService.deleteEvalAnnotation(artifactId, annotationId)
  }

  async createSpanAnnotation(
    artifactId: string,
    traceId: string,
    spanId: string,
    data: AddAnnotationPayload,
  ) {
    return this.apiService.createSpanAnnotation(artifactId, traceId, spanId, data)
  }

  async updateSpanAnnotation(
    artifactId: string,
    annotationId: string,
    data: UpdateAnnotationPayload,
  ) {
    return this.apiService.updateSpanAnnotation(artifactId, annotationId, data)
  }

  async deleteSpanAnnotation(artifactId: string, annotationId: string) {
    return this.apiService.deleteSpanAnnotation(artifactId, annotationId)
  }

  async getSpanAnnotations(artifactId: string, traceId: string, spanId: string) {
    return this.apiService.getSpanAnnotations(artifactId, traceId, spanId)
  }

  async getTracesAnnotationSummary(artifactId: string) {
    return this.apiService.getTracesAnnotationSummary(artifactId)
  }

  async getEvalsDatasetAnnotationsSummary(datasetId: string) {
    const responses = this.artifacts.map(async (artifact) => {
      return this.apiService.getEvalAnnotationSummary(artifact.id, datasetId)
    })
    const annotationsSummaryByArtifact = await Promise.all(responses)
    return annotationsSummaryByArtifact.reduce(
      (acc, summary) => {
        acc.feedback.push(...summary.feedback)
        acc.expectations.push(...summary.expectations)
        return acc
      },
      { feedback: [], expectations: [] },
    )
  }

  async resetEvalsDatasetsRequestParams() {
    this._datasetsCursors = {}
  }

  async resetDatasetPage(datasetId: string) {
    this._datasetsCursors[datasetId] = []
  }

  async getDatasetAverageScores(datasetId: string, search?: string, filters?: string[]) {
    const responses = this.artifacts.map(async (artifact) => {
      const scores = await this.apiService.getExperimentDatasetAverageScores(
        artifact.id,
        datasetId,
        search,
        filters,
      )
      return {
        modelId: artifact.id,
        scores,
      }
    })
    const averageScoresByArtifact = await Promise.all(responses)
    return averageScoresByArtifact.flat()
  }

  async getTraces(params: GetTracesParams) {
    const responses = this.artifacts.map(async (artifact) => {
      const cursors = this._tracesCursors[artifact.id] || []
      const currentCursor = cursors[cursors.length - 1]
      if (currentCursor === null) return []
      const { items, cursor: newCursor } = await this.apiService.getExperimentTraces({
        ...params,
        experiment_id: artifact.id,
        cursor: currentCursor,
      })
      this._tracesCursors[artifact.id] = [...cursors, newCursor]
      return items
    })
    const tracesByArtifact = await Promise.all(responses)
    return tracesByArtifact.flat()
  }

  async getFreshTraces(params: GetTracesParams) {
    const responses = this.artifacts.map(async (artifact) => {
      const cursors = this._tracesCursors[artifact.id] || []
      const cursorsList = [null, ...cursors]
      cursorsList.pop()
      const promises = cursorsList.map(async (cursor) => {
        const { items } = await this.apiService.getExperimentTraces({
          ...params,
          experiment_id: artifact.id,
          cursor,
        })
        return items
      })
      const tracesByCursor = await Promise.all(promises)
      return tracesByCursor.flat()
    })
    const tracesByArtifact = await Promise.all(responses)
    return tracesByArtifact.flat()
  }

  async getAllTraces(params: Omit<GetTracesParams, 'limit'>) {
    const responses = this.artifacts.map(async (artifact) => {
      return this.apiService.getAllExperimentTraces({ ...params, experiment_id: artifact.id })
    })
    const tracesByArtifact = await Promise.all(responses)
    return tracesByArtifact.flat()
  }

  async resetTracesRequestParams(artifactId?: string) {
    if (artifactId) {
      this._tracesCursors[artifactId] = []
    } else {
      this._tracesCursors = {}
    }
  }

  async getEvalById(artifactId: string, evalId: string) {
    const info = await this.apiService.getEvalById(artifactId, evalId)
    return {
      ...info,
      modelId: artifactId,
    }
  }

  async getTracesColumns(artifactId: string): Promise<TypedTracesColumns> {
    return this.apiService.getTypedTracesColumns(artifactId)
  }

  async validateEvalsFilter(filters: string[]): Promise<ValidateResponseItem[]> {
    return this.apiService.validateEvalsFilter(filters)
  }

  async validateTracesFilter(filters: string[]): Promise<ValidateResponseItem[]> {
    return this.apiService.validateTracesFilter(filters)
  }

  async getBatchExperimentEvals(params: GetBatchExperimentsEvalsParams) {
    const { items, cursor } = await this.apiService.getBatchExperimentEvals(params)
    const formattedItems = items.map((item) => ({ ...item, modelId: item.experiment_id }))
    return { items: formattedItems, cursor }
  }

  private prepareMetricData(metricHistory: ExperimentMetricHistory) {
    const initialAcc: ExperimentSnapshotDynamicMetric = {
      x: [],
      y: [],
      modelId: metricHistory.experiment_id,
      aggregated: metricHistory.subsampled ?? false,
    }
    return metricHistory.history.reduce((acc, point) => {
      acc.x.push(point.step)
      acc.y.push(point.value)
      return acc
    }, initialAcc)
  }

  private prepareSpan(span: SpanFromApi, traceId: string): Omit<TraceSpan, 'children'> {
    const { attributes, events, links, status_code, ...data } = span
    return {
      ...data,
      status_code: status_code || 0,
      trace_id: traceId,
      attributes: attributes ? JSON.stringify(attributes) : '',
      events: events ? JSON.stringify(events) : '',
      links: links ? JSON.stringify(links) : '',
    }
  }

  private sortSpans(tree: TraceSpan[]): TraceSpan[] {
    return tree
      .sort((a, b) => {
        return a.start_time_unix_nano - b.start_time_unix_nano
      })
      .map((span) => {
        return {
          ...span,
          children: this.sortSpans(span.children),
        }
      })
  }
}
