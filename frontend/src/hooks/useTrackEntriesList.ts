import type { ITrackArtifact } from '@/lib/api/orbit-tracks/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref } from 'vue'

interface RequestInfo {
  organizationId: string
  orbitId: string
  trackId: string
}

export const useTrackEntriesList = (pageSize = 20) => {
  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const isLoading = ref(false)
  const entriesList = ref<ITrackArtifact[]>([])

  const pageIndex = computed(() => {
    return savedCursors.value.length
  })

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function getInitialPage() {
    isLoading.value = true
    try {
      const response = await getData(null)
      addItemsToList(response.items)
      savedCursors.value.push(response.cursor)
    } finally {
      isLoading.value = false
    }
  }

  async function getNextPage() {
    const cursor = getNextPageCursor()
    if (!cursor) return
    isLoading.value = true
    try {
      const response = await getData(cursor)
      addItemsToList(response.items)
      savedCursors.value.push(response.cursor)
    } finally {
      isLoading.value = false
    }
  }

  async function getData(cursor: string | null) {
    if (!requestInfo.value) throw new Error('Request info not set')
    return await api.orbitTracks.listEntries(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      requestInfo.value.trackId,
      { cursor: cursor ?? undefined, page_size: pageSize },
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

  function addItemsToList(entries: ITrackArtifact[]) {
    const existingIds = entriesList.value.map((entry) => entry.id)
    const newEntries = entries.filter((entry) => !existingIds.includes(entry.id))
    entriesList.value = [...entriesList.value, ...newEntries]
  }

  async function onLazyLoad(event: VirtualScrollerLazyEvent) {
    if (isLoading.value) return
    const { last } = event
    if (last === pageIndex.value * pageSize) {
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
    addItemsToList,
    onLazyLoad,
  }
}
