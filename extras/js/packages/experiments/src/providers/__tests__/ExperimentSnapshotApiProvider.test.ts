import { describe, it, expect, vi } from 'vitest'
import { ExperimentSnapshotApiProvider } from '../ExperimentSnapshotApiProvider'
import type {
  ApiServiceInterface,
  ExperimentMetricHistory,
  SpanFromApi,
} from '../ExperimentSnapshotApiProvider.interface'

async function prepareMetric(history: ExperimentMetricHistory) {
  const apiService = {
    getExperimentMetricHistory: async () => history,
  } as unknown as ApiServiceInterface
  const provider = new ExperimentSnapshotApiProvider(apiService)
  await provider.init({
    artifacts: [{ id: history.experiment_id, dynamicMetrics: ['loss'], staticParams: {} }],
  })
  const [metric] = await provider.getDynamicMetricData('loss')
  return metric
}

describe('ExperimentSnapshotApiProvider.prepareMetricData', () => {
  it('marks the metric aggregated when the API reports subsampled: true', async () => {
    const metric = await prepareMetric({
      experiment_id: 'exp-1',
      subsampled: true,
      history: [
        { step: 1, value: 0.9 },
        { step: 2, value: 0.5 },
      ],
    })

    expect(metric.aggregated).toBe(true)
    expect(metric.x).toEqual([1, 2])
    expect(metric.y).toEqual([0.9, 0.5])
    expect(metric.modelId).toBe('exp-1')
  })

  it('leaves the metric un-aggregated when the API reports subsampled: false', async () => {
    const metric = await prepareMetric({
      experiment_id: 'exp-1',
      subsampled: false,
      history: [{ step: 1, value: 0.9 }],
    })

    expect(metric.aggregated).toBe(false)
  })

  it('defaults aggregated to false when the API omits subsampled', async () => {
    const metric = await prepareMetric({
      experiment_id: 'exp-1',
      history: [{ step: 1, value: 0.9 }],
    })

    expect(metric.aggregated).toBe(false)
  })
})

describe('ExperimentSnapshotApiProvider.getTraceId', () => {
  it('loads the linked trace for the requested model and dataset immediately after init', async () => {
    const getEvalById = vi.fn().mockResolvedValue({ dataset_id: 'ds1', trace_ids: ['t1', 't2'] })
    const provider = new ExperimentSnapshotApiProvider({
      getEvalById,
    } as unknown as ApiServiceInterface)
    await provider.init({ artifacts: [{ id: 'm1', dynamicMetrics: [], staticParams: {} }] })

    expect(await provider.getTraceId({ modelId: 'm1', datasetId: 'ds1', evalId: 'e1' })).toBe('t1')
    expect(getEvalById).toHaveBeenCalledWith('m1', 'e1')
    expect(await provider.getTraceId({ modelId: 'm1', datasetId: 'ds2', evalId: 'e1' })).toBeNull()
  })

  it('returns null when no traces are linked and propagates API errors', async () => {
    const getEvalById = vi.fn().mockResolvedValue({ dataset_id: 'ds1', trace_ids: [] })
    const provider = new ExperimentSnapshotApiProvider({
      getEvalById,
    } as unknown as ApiServiceInterface)
    const params = { modelId: 'm1', datasetId: 'ds1', evalId: 'e1' }
    expect(await provider.getTraceId(params)).toBeNull()
    getEvalById.mockRejectedValue(new Error('Request failed'))
    await expect(provider.getTraceId(params)).rejects.toThrow('Request failed')
  })
})

describe('ExperimentSnapshotApiProvider span payload', () => {
  const span: SpanFromApi = {
    span_id: 's1',
    parent_span_id: null,
    name: 'chat',
    kind: 0,
    dfs_span_type: 1,
    start_time_unix_nano: 1,
    end_time_unix_nano: 2,
    status_code: 1,
    status_message: 'ok',
    attributes: { model: 'gpt-4o' },
    events: null,
    links: null,
    trace_flags: null,
    annotation_count: 0,
  }

  const structureSpan: SpanFromApi = {
    ...span,
    status_message: null,
    attributes: null,
    events: null,
    links: null,
  }

  it('returns full spans marked as loaded when the service has no span endpoint', async () => {
    const getTraceDetails = vi.fn(async () => ({ trace_id: 't1', spans: [span] }))
    const apiService = { getTraceDetails } as unknown as ApiServiceInterface
    const spans = await new ExperimentSnapshotApiProvider(apiService).getTraceSpans('e1', 't1')

    expect(spans).toEqual([
      {
        span_id: 's1',
        parent_span_id: null,
        name: 'chat',
        kind: 0,
        dfs_span_type: 1,
        start_time_unix_nano: 1,
        end_time_unix_nano: 2,
        status_code: 1,
        status_message: 'ok',
        trace_flags: null,
        annotation_count: 0,
        trace_id: 't1',
        attributes: JSON.stringify({ model: 'gpt-4o' }),
        events: '',
        links: '',
        payloadLoaded: true,
      },
    ])
    expect(getTraceDetails).toHaveBeenCalledExactlyOnceWith('e1', 't1')
  })

  it('requests the structure and marks spans as not loaded when the service has a span endpoint', async () => {
    const getTraceDetails = vi.fn(async () => ({ trace_id: 't1', spans: [structureSpan] }))
    const getSpan = vi.fn(async () => span)
    const apiService = { getTraceDetails, getSpan } as unknown as ApiServiceInterface
    const provider = new ExperimentSnapshotApiProvider(apiService)
    const spans = await provider.getTraceSpans('e1', 't1')

    expect(getTraceDetails).toHaveBeenCalledExactlyOnceWith('e1', 't1', { payloads: false })
    expect(getSpan).not.toHaveBeenCalled()
    expect(spans).toMatchObject([
      {
        span_id: 's1',
        trace_id: 't1',
        status_code: 1,
        status_message: null,
        attributes: '',
        events: '',
        links: '',
        payloadLoaded: false,
      },
    ])
    expect(await provider.getSpanPayload('e1', 't1', 's1')).toEqual({
      attributes: JSON.stringify({ model: 'gpt-4o' }),
      events: '',
      links: '',
      status_message: 'ok',
    })
    expect(getTraceDetails).toHaveBeenCalledTimes(1)
  })

  it('builds the same tree from the structure as from full spans', async () => {
    const child: SpanFromApi = {
      ...span,
      span_id: 's2',
      parent_span_id: 's1',
      start_time_unix_nano: 2,
    }
    const strip = (item: SpanFromApi): SpanFromApi => ({
      ...item,
      status_message: null,
      attributes: null,
      events: null,
      links: null,
    })
    const full = new ExperimentSnapshotApiProvider({
      getTraceDetails: async () => ({ trace_id: 't1', spans: [child, span] }),
    } as unknown as ApiServiceInterface)
    const lazy = new ExperimentSnapshotApiProvider({
      getTraceDetails: async () => ({ trace_id: 't1', spans: [strip(child), strip(span)] }),
      getSpan: async () => span,
    } as unknown as ApiServiceInterface)
    const ids = (tree: { span_id: string; children: unknown[] }[]): unknown =>
      tree.map((node) => [node.span_id, ids(node.children as typeof tree)])

    const fullTree = await full.buildSpanTree((await full.getTraceSpans('e1', 't1')) ?? [])
    const lazyTree = await lazy.buildSpanTree((await lazy.getTraceSpans('e1', 't1')) ?? [])

    expect(ids(lazyTree)).toEqual(ids(fullTree))
    expect(ids(lazyTree)).toEqual([['s1', [['s2', []]]]])
  })

  it('reads one span from the trace when the service has no span endpoint', async () => {
    const getTraceDetails = vi.fn(async () => ({ trace_id: 't1', spans: [span] }))
    const apiService = { getTraceDetails } as unknown as ApiServiceInterface
    const provider = new ExperimentSnapshotApiProvider(apiService)

    expect(await provider.getSpanPayload('e1', 't1', 's1')).toEqual({
      attributes: JSON.stringify({ model: 'gpt-4o' }),
      events: '',
      links: '',
      status_message: 'ok',
    })
    expect(getTraceDetails).toHaveBeenCalledWith('e1', 't1')
    await expect(provider.getSpanPayload('e1', 't1', 'missing')).rejects.toThrow('Span not found')
  })

  it('uses the span endpoint when the service has one', async () => {
    const getSpan = vi.fn(async () => span)
    const getTraceDetails = vi.fn()
    const apiService = { getSpan, getTraceDetails } as unknown as ApiServiceInterface
    const payload = await new ExperimentSnapshotApiProvider(apiService).getSpanPayload(
      'e1',
      't1',
      's1',
    )

    expect(payload.attributes).toBe(JSON.stringify({ model: 'gpt-4o' }))
    expect(getSpan).toHaveBeenCalledWith('e1', 't1', 's1')
    expect(getTraceDetails).not.toHaveBeenCalled()
  })

  it('rejects when the span endpoint fails', async () => {
    const notFound = { response: { status: 404, data: { detail: 'Span not found' } } }
    const apiService = {
      getSpan: vi.fn().mockRejectedValue(notFound),
      getTraceDetails: vi.fn(),
    } as unknown as ApiServiceInterface

    await expect(
      new ExperimentSnapshotApiProvider(apiService).getSpanPayload('e1', 't1', 'missing'),
    ).rejects.toBe(notFound)
  })
})
