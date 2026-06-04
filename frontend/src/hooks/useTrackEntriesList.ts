import type { TrackEntry } from '@/lib/api/orbit-tracks/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref } from 'vue'

interface RequestInfo {
  organizationId: string
  orbitId: string
  trackId: string
}

export const useTrackEntriesList = (limit = 20) => {
  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const isLoading = ref(false)
  const stageFilter = ref<string | undefined>(undefined)

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
      { cursor, limit, stage: stageFilter.value },
    )
  }

  function getNextPageCursor() {
    return savedCursors.value[savedCursors.value.length - 1] ?? null
  }

  function reset() {
    entriesList.value = []
    savedCursors.value = []
    requestInfo.value = null
  }

  function addEntriesToList(entries: TrackEntry[]) {
    const existingIds = entriesList.value.map((entry) => entry.id)
    const newEntries = entries.filter((entry) => !existingIds.includes(entry.id))
    entriesList.value = [...entriesList.value, ...newEntries]
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
  }
}
