import type { GetTrackEntriesListParams, TrackEntry } from '@/lib/api/orbit-tracks/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref, watch } from 'vue'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'

interface RequestInfo {
  organizationId: string
  orbitId: string
  trackId: string
}

export const useTrackEntriesList = (limit = 20, syncStore = false) => {
  const artifactLinksStore = useArtifactLinksStore()

  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const isLoading = ref(false)
  const stageFilter = ref<string | undefined>(undefined)
  const sortData = ref<Pick<GetTrackEntriesListParams, 'sort_by' | 'order'>>({
    sort_by: undefined,
    order: undefined,
  })

  function setSortData(data: Pick<GetTrackEntriesListParams, 'sort_by' | 'order'>) {
    sortData.value = data
  }

  const entriesList = ref<TrackEntry[]>([])

  const pageIndex = computed(() => {
    return savedCursors.value.length
  })

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function getInitialPage() {
    isLoading.value = true
    const cursor = null
    const response = await getEntriesData(cursor)
    addEntriesToList(response.items)
    savedCursors.value.push(response.cursor)
    isLoading.value = false
  }

  async function getNextPage() {
    const cursor = getNextPageCursor()
    if (!cursor) return
    isLoading.value = true
    const response = await getEntriesData(cursor)
    addEntriesToList(response.items)
    savedCursors.value.push(response.cursor)
    isLoading.value = false
  }

  async function getEntriesData(cursor: string | null) {
    if (!requestInfo.value) throw new Error('Request info not set')
    return await api.orbitTracks.listEntries(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.trackId,
      { cursor, limit, stage: stageFilter.value, ...sortData.value },
    )
  }

  function getNextPageCursor() {
    return savedCursors.value[savedCursors.value.length - 1] ?? null
  }

  function reset() {
    setEntriesList([])
    savedCursors.value = []
    requestInfo.value = null
  }

  function addEntriesToList(entries: TrackEntry[]) {
    const existingIds = entriesList.value.map((entry) => entry.id)
    const newEntries = entries.filter((entry) => !existingIds.includes(entry.id))
    setEntriesList([...entriesList.value, ...newEntries])
  }

  function setStageFilter(stageId: string | undefined) {
    stageFilter.value = stageId
  }

  async function onLazyLoad(event: VirtualScrollerLazyEvent) {
    if (isLoading.value) return
    const { last } = event
    if (last === pageIndex.value * limit) {
      await getNextPage()
    }
  }

  function setEntriesList(entries: TrackEntry[]) {
    if (syncStore) {
      artifactLinksStore.setEntriesList(entries)
    } else {
      entriesList.value = entries
    }
  }

  if (syncStore) {
    watch(
      () => artifactLinksStore.entriesList,
      (storedEntriesList) => {
        entriesList.value = storedEntriesList
      },
      { immediate: true },
    )
  }

  return {
    setRequestInfo,
    getInitialPage,
    entriesList,
    getNextPage,
    isLoading,
    pageIndex,
    reset,
    addEntriesToList,
    stageFilter,
    setStageFilter,
    onLazyLoad,
    sortData,
    setSortData,
  }
}
