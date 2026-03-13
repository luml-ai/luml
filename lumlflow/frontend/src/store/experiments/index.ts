import type { Experiment, UpdateExperimentPayload } from './experiments.interface'
import type { GetExperimentsParams } from '@/api/api.interface'
import { defineStore } from 'pinia'
import { ref, watch } from 'vue'
import { useToast } from 'primevue'
import { errorToast, successToast } from '@/toasts'
import { usePagination } from '@/hooks/usePagination'
import { apiService } from '@/api/api.service'
import { useDebounceFn } from '@vueuse/core'

export const useExperimentsStore = defineStore('experiments', () => {
  const toast = useToast()
  const { data, getInitialPage, getNextPage, setParams, onLazyLoad, getParams, isLoading, reset } =
    usePagination<Experiment, GetExperimentsParams>(apiService.getExperiments)

  const queryParams = ref<Partial<GetExperimentsParams>>({})

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

  async function deleteExperiments(experimentIds: string[]) {
    const promises = experimentIds.map((experimentId) => apiService.deleteExperiment(experimentId))
    const results = await Promise.allSettled(promises)
    const deletedExperimentIds = results
      .filter((result) => result.status === 'fulfilled')
      .map((result) => result.value.id)
    setSelectedExperiments([])
    setEditableExperiment(null)
    toast.add(successToast(`${deletedExperimentIds.length} experiments deleted successfully`))
    await getInitialPage()
  }

  async function updateExperiment(experimentId: string, payload: UpdateExperimentPayload) {
    await apiService.updateExperiment(experimentId, payload)
    await getInitialPage()
    setSelectedExperiments([])
    setEditableExperiment(null)
    toast.add(successToast('Experiment updated successfully'))
  }

  function setQueryParams(params: Partial<GetExperimentsParams>) {
    queryParams.value = params
  }

  async function updatePaginationParams(params: typeof queryParams.value) {
    setParams({ ...getParams(), ...params })
    try {
      await getInitialPage()
    } catch (error) {
      toast.add(errorToast(error))
    }
  }

  const debouncedUpdatePaginationParams = useDebounceFn(updatePaginationParams, 500)

  watch(queryParams, debouncedUpdatePaginationParams, { deep: true })

  return {
    experiments: data,
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
    getInitialPage,
    getNextPage,
    onLazyLoad,
    isLoading,
    setQueryParams,
    queryParams,
    reset,
  }
})
