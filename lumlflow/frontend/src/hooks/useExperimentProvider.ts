import type { Experiment } from '@/store/experiments/experiments.interface'
import { ExperimentSnapshotApiProvider, type ExperimentSnapshotProvider } from '@luml/experiments'
import { apiService } from '@/api/api.service'
import { useExperimentStore } from '@/store/experiment'
import { ref, watch, type Ref } from 'vue'

export const useExperimentProvider = (): { provider: Ref<ExperimentSnapshotProvider | null> } => {
  const experimentStore = useExperimentStore()

  const provider = ref<ExperimentSnapshotProvider | null>(null)

  async function createProvider(experiment: Experiment) {
    const newProvider = new ExperimentSnapshotApiProvider(apiService)
    const experimentMainInfo = {
      id: experiment.id,
      dynamicMetrics: Object.keys(experiment.dynamic_params || []),
    }
    await newProvider.init({ artifacts: [experimentMainInfo] })
    provider.value = newProvider
  }

  function resetProvider() {
    provider.value = null
  }

  watch(
    () => experimentStore.experiment,
    (experiment) => {
      if (experiment) createProvider(experiment)
      else resetProvider()
    },
    {
      immediate: true,
    },
  )

  return {
    provider,
  }
}
