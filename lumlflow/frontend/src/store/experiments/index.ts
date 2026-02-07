import type { Experiment, UpdateExperimentPayload } from './experiments.interface'
import { defineStore } from 'pinia'
import { ref } from 'vue'
import { MOCK_EXPERIMENTS } from './experiments.mock'
import { useToast } from 'primevue'
import { successToast } from '@/toasts'

export const useExperimentsStore = defineStore('experiments', () => {
  const toast = useToast()

  const experiments = ref<Experiment[]>(MOCK_EXPERIMENTS)
  const selectedExperiments = ref<Experiment[]>([])
  const tableColumns = ref<string[]>([])
  const visibleColumns = ref<string[]>([])
  const editableExperiment = ref<Experiment | null>(null)

  function setEditableExperiment(experiment: Experiment | null) {
    editableExperiment.value = experiment
  }

  function setSelectedExperiments(experiments: Experiment[]) {
    selectedExperiments.value = experiments
  }

  function setTableColumns(columns: string[]) {
    tableColumns.value = columns
  }

  function setVisibleColumns(columns: string[]) {
    visibleColumns.value = columns
  }

  function deleteExperiments(experimentIds: string[]) {
    experiments.value = experiments.value.filter(
      (experiment) => !experimentIds.includes(experiment.id),
    )
    setSelectedExperiments([])
    setEditableExperiment(null)
    toast.add(successToast(`${experimentIds.length} experiments deleted successfully`))
  }

  function updateExperiment(experimentId: string, payload: UpdateExperimentPayload) {
    experiments.value = experiments.value.map((experiment) => {
      if (experiment.id !== experimentId) return experiment
      return { ...experiment, ...payload }
    })
    setSelectedExperiments([])
    setEditableExperiment(null)
  }

  return {
    experiments,
    selectedExperiments,
    setSelectedExperiments,
    tableColumns,
    visibleColumns,
    setTableColumns,
    setVisibleColumns,
    deleteExperiments,
    editableExperiment,
    setEditableExperiment,
    updateExperiment,
  }
})
