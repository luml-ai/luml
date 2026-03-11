import type {
  EvalsColumns,
  EvalsInfo,
  ExperimentSnapshotDynamicMetric,
  ExperimentSnapshotProvider,
  GetEvalsByDatasetParams,
  SpansListType,
  SpansParams,
  TraceSpan,
} from '@/interfaces/interfaces'
import type {
  ArtifactInfo,
  TraceInfo,
  ApiServiceInterface,
  ExperimentMetricHistory,
  SpanFromApi,
} from './ExperimentSnapshotApiProvider.interface'
import type {
  AddAnnotationPayload,
  UpdateAnnotationPayload,
} from '@/components/annotations/annotations.interface'

export class ExperimentSnapshotApiProvider implements ExperimentSnapshotProvider {
  private traces: TraceInfo[] = []
  private _artifacts: ArtifactInfo[] | null = null
  private _datasetsCursors: Record<string, Array<string | null>> = {}

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
  }

  async getDynamicMetricsNames() {
    return this.artifacts.map((artifact) => artifact.dynamicMetrics).flat()
  }

  async getDynamicMetricData(metricName: string) {
    const promises = this.artifacts.map(async (artifact) => {
      const data = await this.apiService.getExperimentMetricHistory(artifact.id, metricName)
      return this.prepareMetricData(data)
    })
    return Promise.all(promises)
  }

  async getStaticParamsList() {
    return []
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
    return (
      this.traces.find(
        (item) =>
          item.artifactId === params.modelId &&
          item.datasetId === params.datasetId &&
          item.evalId === params.evalId,
      )?.tracesIds?.[0] || null
    )
  }

  async getUniqueTraceIds(modelId: string): Promise<string[]> {
    const { items } = await this.apiService.getExperimentTraces({ experiment_id: modelId })
    return items.map((item) => item.trace_id)
  }

  async getEvalsColumns(datasetId: string): Promise<EvalsColumns> {
    const responses = this.artifacts.map(async (artifact) => {
      return this.apiService.getExperimentEvalColumns(artifact.id, datasetId)
    })
    const columnsByArtifact = await Promise.all(responses)
    const columnsSets = columnsByArtifact.reduce(
      (acc, columns) => {
        columns.inputs.forEach((item) => acc.inputs.add(item))
        columns.outputs.forEach((item) => acc.outputs.add(item))
        columns.refs.forEach((item) => acc.refs.add(item))
        columns.scores.forEach((item) => acc.scores.add(item))
        columns.metadata.forEach((item) => acc.metadata.add(item))
        return acc
      },
      {
        inputs: new Set<string>(),
        outputs: new Set<string>(),
        refs: new Set<string>(),
        scores: new Set<string>(),
        metadata: new Set<string>(),
      },
    )
    return {
      inputs: Array.from(columnsSets.inputs),
      outputs: Array.from(columnsSets.outputs),
      refs: Array.from(columnsSets.refs),
      scores: Array.from(columnsSets.scores),
      metadata: Array.from(columnsSets.metadata),
    }
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

  async getDatasetAverageScores(datasetId: string) {
    const responses = this.artifacts.map(async (artifact) => {
      const scores = await this.apiService.getExperimentDatasetAverageScores(artifact.id, datasetId)
      return {
        modelId: artifact.id,
        scores,
      }
    })
    const averageScoresByArtifact = await Promise.all(responses)
    return averageScoresByArtifact.flat()
  }

  private prepareMetricData(metricHistory: ExperimentMetricHistory) {
    const initialAcc: ExperimentSnapshotDynamicMetric = {
      x: [],
      y: [],
      modelId: metricHistory.experiment_id,
      aggregated: false,
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
