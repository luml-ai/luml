import type { ExperimentSnapshotProvider } from '@luml/experiments'
import type { Experiment, ExperimentMetricHistory } from '@/store/experiments/experiments.interface'
import type {
  EvalsListType,
  ExperimentSnapshotDynamicMetric,
  SpansListType,
  SpansParams,
  TraceSpan,
} from '../../../../extras/js/packages/experiments/dist/interfaces/interfaces'
import { useExperimentStore } from '@/store/experiment'
import { ref, watch } from 'vue'
import { apiService } from '@/api/api.service'

import type { Span } from '@/store/experiments/experiments.interface'

interface ArtifactInfo {
  id: string
  dynamicMetrics: string[]
}

interface TraceInfo {
  artifactId: string
  datasetId: string
  tracesIds: string[]
  evalId: string
}

class ExperimentSnapshotApiProvider implements ExperimentSnapshotProvider {
  private traces: TraceInfo[] = []
  private _artifacts: ArtifactInfo[] | null = null

  get artifacts() {
    if (!this._artifacts) throw new Error('Experiments not initialized')
    return this._artifacts
  }

  set artifacts(value: ArtifactInfo[]) {
    this._artifacts = value
  }

  constructor() {}

  async init(data: ArtifactInfo[]) {
    this._artifacts = data
  }

  async getDynamicMetricsNames() {
    return this.artifacts.map((artifact) => artifact.dynamicMetrics).flat()
  }

  async getDynamicMetricData(metricName: string) {
    const promises = this.artifacts.map(async (artifact) => {
      const data = await apiService.getExperimentMetricHistory(artifact.id, metricName)
      return this.prepareMetricData(data)
    })
    return Promise.all(promises)
  }

  async getStaticParamsList() {
    return []
  }

  async getEvalsList() {
    this.resetTraces()
    const promises = this.artifacts.map(async (artifact) => {
      const { items } = await apiService.getExperimentEvals({ experiment_id: artifact.id })
      return items
    })
    const results = await Promise.all(promises)
    const evalsList: EvalsListType = {}
    results.forEach((item, experimentIndex) => {
      item.forEach((datasetInfo) => {
        const datasetId = datasetInfo.dataset_id
        const experimentId = this.artifacts[experimentIndex].id
        if (!evalsList[datasetId]) {
          evalsList[datasetId] = []
        }
        this.traces.push({
          artifactId: experimentId,
          datasetId,
          tracesIds: datasetInfo.trace_ids,
          evalId: datasetInfo.id,
        })
        const { created_at, updated_at, trace_ids, ...data } = datasetInfo
        evalsList[datasetId].push({ ...data, modelId: experimentId })
      })
    })
    return evalsList
  }

  async getTraceSpans(modelId: string, traceId: string): Promise<SpansListType> {
    const { spans, trace_id } = await apiService.getTraceDetails(modelId, traceId)
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

  async getUniqueTraceIds(modelId: string) {
    const { items } = await apiService.getExperimentTraces({ experiment_id: modelId })
    return items.map((item) => item.trace_id)
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

  private prepareSpan(span: Span, traceId: string): Omit<TraceSpan, 'children'> {
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

  private resetTraces() {
    this.traces = []
  }
}

export const useExperimentProvider = () => {
  const experimentStore = useExperimentStore()

  const provider = ref<ExperimentSnapshotProvider | null>(null)

  function createProvider(experiment: Experiment) {
    provider.value = new ExperimentSnapshotApiProvider()
    provider.value.init([
      { id: experiment.id, dynamicMetrics: Object.keys(experiment.dynamic_params || {}) },
    ])
  }

  function resetProvider() {
    provider.value = null
  }

  watch(
    () => experimentStore.experiment,
    (experiment) => {
      experiment ? createProvider(experiment) : resetProvider()
    },
    {
      immediate: true,
    },
  )

  return {
    provider,
  }
}
