import type { GetModelsListParams, MlModel } from '@/lib/api/orbit-ml-models/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref, watch } from 'vue'
import { useModelsStore } from '@/stores/models'

interface RequestInfo {
  organizationId: string
  orbitId: string
  collectionId: string
}

export const useModelsList = (limit = 20, syncStore = true) => {
  const modelsStore = useModelsStore()
  const abortController = ref<AbortController | null>(null)

  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const isLoading = ref(false)
  const sortData = ref<Pick<GetModelsListParams, 'sort_by' | 'order'>>({
    sort_by: undefined,
    order: undefined,
  })

  const modelsList = ref<MlModel[]>([])

  const pageIndex = computed(() => {
    return savedCursors.value.length
  })

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function getInitialPage() {
    isLoading.value = true
    const cursor = null
    const response = await getModelsData(cursor)
    addModelsToList(response.items)
    savedCursors.value.push(response.cursor)
    isLoading.value = false
  }

  async function getNextPage() {
    const cursor = getNextPageCursor()
    if (!cursor) return
    isLoading.value = true
    const response = await getModelsData(cursor)
    addModelsToList(response.items)
    savedCursors.value.push(response.cursor)
    isLoading.value = false
  }

  async function getModelsData(cursor: string | null) {
    if (!requestInfo.value) throw new Error('Request info not set')
    abortController.value?.abort()
    abortController.value = new AbortController()
    return await api.mlModels.getModelsList(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      { cursor, limit, ...sortData.value },
      abortController.value.signal,
    )
  }

  function getNextPageCursor() {
    return savedCursors.value[savedCursors.value.length - 1] ?? null
  }

  function reset() {
    setModelsList([])
    savedCursors.value = []
    requestInfo.value = null
  }

  function addModelsToList(models: MlModel[]) {
    const existingModelsIds = modelsList.value.map((model) => model.id)
    const newModels = models.filter((model) => !existingModelsIds.includes(model.id))
    setModelsList([...modelsList.value, ...newModels])
  }

  function setSortData(data: Pick<GetModelsListParams, 'sort_by' | 'order'>) {
    sortData.value = data
  }

  async function onLazyLoad(event: VirtualScrollerLazyEvent) {
    if (isLoading.value) return
    const { last } = event
    if (last === pageIndex.value * limit) {
      await getNextPage()
    }
  }

  function setModelsList(models: MlModel[]) {
    if (syncStore) {
      modelsStore.setModelsList(models)
    } else {
      modelsList.value = models
    }
  }

  async function onSortDataChange() {
    setModelsList([])
    savedCursors.value = []
    getInitialPage()
  }

  function setLoading(value: boolean) {
    isLoading.value = value
  }

  if (syncStore) {
    watch(
      () => modelsStore.modelsList,
      (storeModelsList) => {
        modelsList.value = storeModelsList
      },
      { immediate: true },
    )
  }

  watch(sortData, onSortDataChange)

  return {
    setRequestInfo,
    getInitialPage,
    modelsList,
    getNextPage,
    isLoading,
    pageIndex,
    reset,
    addModelsToList,
    setSortData,
    onLazyLoad,
    setLoading,
  }
}
