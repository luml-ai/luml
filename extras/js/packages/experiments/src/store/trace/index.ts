import type { Trace } from '@experiments/providers/ExperimentSnapshotApiProvider.interface'
import type { GetTracesParams, TypedColumnInfo, TypedTracesColumns } from '@experiments/interfaces/interfaces'
import { defineStore } from 'pinia'
import { computed, ref, watch } from 'vue'
import { INITIAL_REQUEST_PARAMS } from './trace.data'
import { useEvalsStore } from '../evals'
import { useDebounceFn } from '@vueuse/core'
import { useAnnotationsStore } from '../annotations'
import { useToast } from 'primevue'
import { simpleErrorToast } from '@experiments/lib/primevue/data/toasts'
import { getErrorMessage } from '@experiments/helpers/helpers'

export const useTraceStore = defineStore('trace', () => {
  const evalsStore = useEvalsStore()
  const annotationsStore = useAnnotationsStore()
  const toast = useToast()

  const requestParams = ref<GetTracesParams>({ ...INITIAL_REQUEST_PARAMS })
  const traces = ref<Trace[]>([])
  const loading = ref(false)
  const artifactId = ref<string | null>(null)
  const typedColumns = ref<TypedTracesColumns | null>(null)

  const typedColumnsList = computed<TypedColumnInfo[]>(() => {
    if (!typedColumns.value) return []
    const entries = Object.entries(typedColumns.value)
    const formattedEntries = entries.map(([key, list]) => {
      return list.map((item) => ({ name: key + '.' + item.name, type: item.type }))
    })
    return formattedEntries.flat()
  })

  async function getNextPage(reset: boolean = false) {
    const params = JSON.parse(JSON.stringify(requestParams.value))
    if (reset) {
      evalsStore.getProvider.resetTracesRequestParams()
    }
    const data = await evalsStore.getProvider.getTraces(params)
    if (reset) {
      traces.value = []
    }
    traces.value = [...traces.value, ...data]
    if (reset && artifactId.value) {
      await annotationsStore.getTracesAnnotationSummary(artifactId.value)
    }
  }

  function setRequestParams(params: Partial<GetTracesParams>) {
    requestParams.value = { ...requestParams.value, ...params }
  }

  function setLoading(value: boolean) {
    loading.value = value
  }

  function setArtifactId(id: string) {
    artifactId.value = id
  }

  function reset() {
    requestParams.value = { ...INITIAL_REQUEST_PARAMS }
    evalsStore.getProvider.resetTracesRequestParams()
    traces.value = []
    loading.value = false
    artifactId.value = null
  }

  async function refresh() {
    if (loading.value) return
    setLoading(true)
    try {
      const params = JSON.parse(JSON.stringify(requestParams.value))
      const data = await evalsStore.getProvider.getFreshTraces(params)
      traces.value = [...data]
      if (artifactId.value) {
        await annotationsStore.getTracesAnnotationSummary(artifactId.value)
      }
    } catch (error) {
      toast.add(simpleErrorToast(getErrorMessage(error)))
    } finally {
      setLoading(false)
    }
  }

  const debouncedRequestParamsChange = useDebounceFn(async () => {
    try {
      if (loading.value) return
      setLoading(true)
      await getNextPage(true)
    } catch (error) {
      toast.add(simpleErrorToast(getErrorMessage(error)))
    } finally {
      setLoading(false)
    }
  }, 500)

  async function getTypedColumns() {
    if (!artifactId.value) return
    const data = await evalsStore.getProvider.getTracesColumns(artifactId.value)
    typedColumns.value = data
  }

  watch(requestParams, debouncedRequestParamsChange, { deep: true })

  return {
    traces,
    requestParams,
    setRequestParams,
    loading,
    getNextPage,
    setLoading,
    reset,
    setArtifactId,
    refresh,
    getTypedColumns,
    typedColumns,
    typedColumnsList,
  }
})
