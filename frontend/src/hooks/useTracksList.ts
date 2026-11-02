import type { Track } from '@/lib/api/orbit-tracks/interfaces'
import type { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { api } from '@/lib/api'
import { computed, ref, watch } from 'vue'
import { usePageLoading } from '@/hooks/usePageLoading'
import { useTracksStore } from '@/stores/tracks'

interface RequestInfo {
  organizationId: string
  orbitId: string
}

export const useTracksList = (limit = 20, syncStore = true, types?: ArtifactTypeEnum[]) => {
  const tracksStore = useTracksStore()

  const savedCursors = ref<Array<string | null>>([])
  const requestInfo = ref<RequestInfo | null>(null)
  const { isLoading, invalidate, track } = usePageLoading()
  const searchQuery = ref<string>('')
  const typesQuery = ref<ArtifactTypeEnum[]>(types ?? [])

  const tracksList = ref<Track[]>([])

  const pageIndex = computed(() => {
    return savedCursors.value.length
  })

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function getInitialPage() {
    invalidate()
    await track(async (isCurrent) => {
      const response = await getTracksData(null)
      if (!isCurrent()) return
      addTracksToList(response.items)
      savedCursors.value.push(response.cursor)
    })
  }

  async function getNextPage() {
    const cursor = getNextPageCursor()
    if (!cursor) return
    await track(async (isCurrent) => {
      const response = await getTracksData(cursor)
      if (!isCurrent()) return
      addTracksToList(response.items)
      savedCursors.value.push(response.cursor)
    })
  }

  async function getTracksData(cursor: string | null) {
    if (!requestInfo.value) throw new Error('Request info not set')
    return await api.orbitTracks.listTracks(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      { cursor, limit, search: searchQuery.value, types: typesQuery.value },
    )
  }

  function getNextPageCursor() {
    return savedCursors.value[savedCursors.value.length - 1] ?? null
  }

  function reset() {
    invalidate()
    setTracksList([])
    savedCursors.value = []
    requestInfo.value = null
  }

  function addTracksToList(tracks: Track[]) {
    const existingTracksIds = tracksList.value.map((track) => track.id)
    const newTracks = tracks.filter((track) => !existingTracksIds.includes(track.id))
    setTracksList([...tracksList.value, ...newTracks])
  }

  function setTracksList(tracks: Track[]) {
    if (syncStore) {
      tracksStore.setTracksList(tracks)
    } else {
      tracksList.value = tracks
    }
  }

  function setSearchQuery(query: string) {
    searchQuery.value = query
  }

  async function onLazyLoad(event: VirtualScrollerLazyEvent) {
    if (isLoading.value) return
    const { last } = event
    if (last >= tracksList.value.length) {
      await getNextPage()
    }
  }

  function setTypesQuery(types: ArtifactTypeEnum[]) {
    typesQuery.value = types
  }

  if (syncStore) {
    watch(
      () => tracksStore.tracksList,
      (storeTracksList) => {
        tracksList.value = storeTracksList
      },
      { immediate: true },
    )
  }

  return {
    setRequestInfo,
    getInitialPage,
    tracksList,
    getNextPage,
    isLoading,
    pageIndex,
    reset,
    addTracksToList,
    searchQuery,
    setSearchQuery,
    onLazyLoad,
    typesQuery,
    setTypesQuery,
  }
}
