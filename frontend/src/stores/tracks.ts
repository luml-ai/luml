import type {
  Track,
  TrackCreateIn,
  TrackEntry,
  TrackEntryCreateIn,
  TrackEntryUpdateIn,
  TrackStageCreateIn,
  TrackStageUpdateIn,
  TrackUpdateIn,
} from '@/lib/api/orbit-tracks/interfaces'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'

export const useTracksStore = defineStore('tracks', () => {
  const route = useRoute()

  const tracksList = ref<Track[]>([])
  const currentTrack = ref<Track | null>(null)
  const artifactEntries = ref<TrackEntry[]>([])
  const creatorVisible = ref(false)

  const requestInfo = computed(() => {
    if (typeof route.params.organizationId !== 'string')
      throw new Error('Current organization not found')
    if (typeof route.params.id !== 'string') throw new Error('Orbit was not found')
    return {
      organizationId: route.params.organizationId,
      orbitId: route.params.id,
    }
  })

  // --- Tracks ---

  async function createTrack(payload: TrackCreateIn, requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    const track = await api.orbitTracks.createTrack(info.organizationId, info.orbitId, payload)
    setTracksList([...tracksList.value, track])
  }

  async function updateTrack(trackId: string, payload: TrackUpdateIn) {
    const updatedTrack = await api.orbitTracks.updateTrack(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      payload,
    )
    const newTracks = tracksList.value.map((track) => {
      return track.id === trackId ? updatedTrack : track
    })
    setTracksList(newTracks)
    if (currentTrack.value?.id === trackId) {
      currentTrack.value = updatedTrack
    }
  }

  async function deleteTrack(trackId: string) {
    await api.orbitTracks.deleteTrack(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
    )
    const newTracks = tracksList.value.filter((track) => track.id !== trackId)
    setTracksList(newTracks)
  }

  function setTracksList(tracks: Track[]) {
    tracksList.value = tracks
  }

  async function setCurrentTrack(trackId: string) {
    const { organizationId, orbitId } = requestInfo.value
    currentTrack.value = await api.orbitTracks.getTrack(organizationId, orbitId, trackId)
  }

  function resetCurrentTrack() {
    currentTrack.value = null
  }

  function reset() {
    tracksList.value = []
    resetCurrentTrack()
    artifactEntries.value = []
  }

  function showCreator() {
    creatorVisible.value = true
  }

  function hideCreator() {
    creatorVisible.value = false
  }

  // --- Entries ---

  async function addEntry(trackId: string, payload: TrackEntryCreateIn) {
    return await api.orbitTracks.addEntry(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      payload,
    )
  }

  async function patchEntry(
    trackId: string,
    entryId: string,
    payload: TrackEntryUpdateIn,
    force?: boolean,
  ) {
    return await api.orbitTracks.patchEntry(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      entryId,
      payload,
      force,
    )
  }

  async function deleteEntry(trackId: string, entryId: string) {
    await api.orbitTracks.deleteEntry(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      entryId,
    )
  }

  async function listArtifactEntries(artifactId: string) {
    artifactEntries.value = await api.orbitTracks.listArtifactEntries(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      artifactId,
    )
  }

  // --- Stages ---

  async function createStage(trackId: string, payload: TrackStageCreateIn) {
    return await api.orbitTracks.createStage(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      payload,
    )
  }

  async function listStages(trackId: string) {
    return await api.orbitTracks.listStages(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
    )
  }

  async function updateStage(trackId: string, stageId: string, payload: TrackStageUpdateIn) {
    return await api.orbitTracks.updateStage(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      stageId,
      payload,
    )
  }

  async function deleteStage(trackId: string, stageId: string, force?: boolean) {
    await api.orbitTracks.deleteStage(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      stageId,
      force,
    )
  }

  return {
    tracksList,
    setTracksList,
    currentTrack,
    artifactEntries,
    creatorVisible,
    requestInfo,
    createTrack,
    updateTrack,
    deleteTrack,
    reset,
    setCurrentTrack,
    resetCurrentTrack,
    showCreator,
    hideCreator,
    addEntry,
    patchEntry,
    deleteEntry,
    listArtifactEntries,
    createStage,
    listStages,
    updateStage,
    deleteStage,
  }
})
