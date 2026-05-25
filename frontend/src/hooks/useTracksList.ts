import type { ITrack } from '@/lib/api/orbit-tracks/interfaces'
import { api } from '@/lib/api'
import { ref, watch } from 'vue'
import { useTracksStore } from '@/stores/tracks'

interface RequestInfo {
  organizationId: string
  orbitId: string
}

export const useTracksList = (syncStore = true) => {
  const tracksStore = useTracksStore()

  const requestInfo = ref<RequestInfo | null>(null)
  const isLoading = ref(false)
  const tracksList = ref<ITrack[]>([])

  function setRequestInfo(info: RequestInfo) {
    requestInfo.value = info
  }

  async function load() {
    if (!requestInfo.value) throw new Error('Request info not set')
    isLoading.value = true
    try {
      const response = await api.orbitTracks.listTracks(
        requestInfo.value.organizationId,
        requestInfo.value.orbitId,
      )
      setList(response.items)
    } finally {
      isLoading.value = false
    }
  }

  function setList(tracks: ITrack[]) {
    if (syncStore) {
      tracksStore.setTracksList(tracks)
    } else {
      tracksList.value = tracks
    }
  }

  function reset() {
    setList([])
    requestInfo.value = null
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
    load,
    tracksList,
    isLoading,
    reset,
  }
}
