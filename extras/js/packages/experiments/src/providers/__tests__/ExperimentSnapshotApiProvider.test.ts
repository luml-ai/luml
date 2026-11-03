import { describe, it, expect, vi } from 'vitest'
import { ExperimentSnapshotApiProvider } from '../ExperimentSnapshotApiProvider'
import type {
  ApiServiceInterface,
  ExperimentMetricHistory,
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
