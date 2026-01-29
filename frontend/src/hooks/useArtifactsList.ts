import type { GetArtifactsListParams, Artifact } from '@/lib/api/artifacts/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref, watch } from 'vue'
import { useArtifactsStore } from '@/stores/artifacts'

interface RequestInfo {
  organizationId: string
  orbitId: string
  collectionId: string
}

export const useArtifactsList = (limit = 20, syncStore = true) => {
  const artifactsStore = useArtifactsStore()

  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const isLoading = ref(false)
  const sortData = ref<Pick<GetArtifactsListParams, 'sort_by' | 'order'>>({
    sort_by: undefined,
    order: undefined,
  })

  const list = ref<Artifact[]>([])

  const pageIndex = computed(() => {
    return savedCursors.value.length
  })

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function getInitialPage() {
    isLoading.value = true
    const cursor = null
    const response = await getData(cursor)
    addItemsToList(response.items)
    savedCursors.value.push(response.cursor)
    isLoading.value = false
  }

  async function getNextPage() {
    const cursor = getNextPageCursor()
    if (!cursor) return
    isLoading.value = true
    const response = await getData(cursor)
    addItemsToList(response.items)
    savedCursors.value.push(response.cursor)
    isLoading.value = false
  }

  async function getData(cursor: string | null) {
    if (!requestInfo.value) throw new Error('Request info not set')
    return await api.artifacts.getList(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.collectionId,
      { cursor, limit, ...sortData.value },
    )
  }

  function getNextPageCursor() {
    return savedCursors.value[savedCursors.value.length - 1] ?? null
  }

  function reset() {
    setList([])
    savedCursors.value = []
    requestInfo.value = null
  }

  function addItemsToList(artifacts: Artifact[]) {
    const existingArtifactsIds = list.value.map((artifact) => artifact.id)
    const newArtifacts = artifacts.filter((artifact) => !existingArtifactsIds.includes(artifact.id))
    setList([...list.value, ...newArtifacts])
  }

  function setSortData(data: Pick<GetArtifactsListParams, 'sort_by' | 'order'>) {
    sortData.value = data
  }

  async function onLazyLoad(event: VirtualScrollerLazyEvent) {
    if (isLoading.value) return
    const { last } = event
    if (last === pageIndex.value * limit) {
      await getNextPage()
    }
  }

  function setList(artifacts: Artifact[]) {
    if (syncStore) {
      artifactsStore.setArtifactsList(artifacts)
    } else {
      list.value = artifacts
    }
  }

  if (syncStore) {
    watch(
      () => artifactsStore.artifactsList,
      (storedList) => {
        list.value = storedList
      },
      { immediate: true },
    )
  }

  return {
    setRequestInfo,
    getInitialPage,
    list,
    getNextPage,
    isLoading,
    pageIndex,
    reset,
    addItemsToList,
    setSortData,
    onLazyLoad,
  }
}
