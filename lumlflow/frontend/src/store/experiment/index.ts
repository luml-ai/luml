import type { Experiment } from '../experiments/experiments.interface'
import { ref } from 'vue'
import { defineStore } from 'pinia'
import { apiService } from '@/api/api.service'

export const useExperimentStore = defineStore('experiment', () => {
  const experiment = ref<Experiment | null>(null)

  async function fetchExperiment(experimentId: string) {
    experiment.value = await apiService.getExperiment(experimentId)
  }

  function resetExperiment() {
    experiment.value = null
  }

  return {
    experiment,
    fetchExperiment,
    resetExperiment,
  }
})
