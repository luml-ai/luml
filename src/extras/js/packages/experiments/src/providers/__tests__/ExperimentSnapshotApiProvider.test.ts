import { describe, it, expect } from 'vitest'
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
