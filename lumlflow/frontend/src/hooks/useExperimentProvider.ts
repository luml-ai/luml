import type { Experiment } from '@/store/experiments/experiments.interface'
import { ExperimentSnapshotApiProvider, type ExperimentSnapshotProvider } from '@luml/experiments'
import { apiService } from '@/api/api.service'
import { ref, type Ref } from 'vue'

export const useExperimentProvider = (): {
  provider: Ref<ExperimentSnapshotProvider | null>
  createProvider: (experiments: Experiment[]) => Promise<void>
  resetProvider: () => void
} => {
  const provider = ref<ExperimentSnapshotProvider | null>(null)

  async function createProvider(experiments: Experiment[]) {
    const newProvider = new ExperimentSnapshotApiProvider(apiService)
    const artifacts = experiments.map((experiment) => ({
      id: experiment.id,
      dynamicMetrics: Object.keys(experiment.dynamic_params ?? {}),
      staticParams: experiment.static_params ?? {}
    }))
    await newProvider.init({ artifacts: artifacts })
    provider.value = newProvider
  }

  function resetProvider() {
    provider.value = null
  }

  return {
    provider,
    createProvider,
    resetProvider,
  }
}
