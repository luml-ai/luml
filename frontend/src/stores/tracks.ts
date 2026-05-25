import type {
  ITrack,
  ITrackCreate,
  ITrackUpdate,
  ITrackArtifact,
  ITrackArtifactCreate,
  ITrackArtifactUpdate,
  ITrackStage,
  ITrackStageCreate,
  ITrackStageUpdate,
} from '@/lib/api/orbit-tracks/interfaces'
import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import { api } from '@/lib/api'
import { useRoute } from 'vue-router'

export const useTracksStore = defineStore('tracks', () => {
  const route = useRoute()

  const tracksList = ref<ITrack[]>([])
  const currentTrack = ref<ITrack | null>(null)
  const creatorVisible = ref(false)
  const artifactEntries = ref<ITrackArtifact[]>([])

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

  async function createTrack(payload: ITrackCreate, requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    const track = await api.orbitTracks.createTrack(info.organizationId, info.orbitId, payload)
    setTracksList([...tracksList.value, track])
    return track
  }

  async function updateTrack(trackId: string, payload: ITrackUpdate) {
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
    return updatedTrack
  }

  async function deleteTrack(trackId: string) {
    await api.orbitTracks.deleteTrack(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
    )
    const newTracks = tracksList.value.filter((track) => track.id !== trackId)
    setTracksList(newTracks)
    if (currentTrack.value?.id === trackId) {
      currentTrack.value = null
    }
  }

  async function getTrack(trackId: string) {
    return await api.orbitTracks.getTrack(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
    )
  }

  // --- Entries ---

  async function addEntry(trackId: string, payload: ITrackArtifactCreate) {
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
    payload: ITrackArtifactUpdate,
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

  async function loadArtifactEntries(artifactId: string) {
    const response = await api.orbitTracks.listArtifactEntries(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      artifactId,
    )
    artifactEntries.value = response.items
  }

  // --- Stages ---

  async function createStage(trackId: string, payload: ITrackStageCreate) {
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

  async function updateStage(trackId: string, stageId: string, payload: ITrackStageUpdate) {
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

  // --- Setters ---

  function setTracksList(tracks: ITrack[]) {
    tracksList.value = tracks
  }

  async function setCurrentTrack(trackId: string) {
    const track = await getTrack(trackId)
    currentTrack.value = track
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

  return {
    tracksList,
    setTracksList,
    currentTrack,
    creatorVisible,
    requestInfo,
    artifactEntries,
    createTrack,
    updateTrack,
    deleteTrack,
    getTrack,
    addEntry,
    patchEntry,
    deleteEntry,
    loadArtifactEntries,
    createStage,
    listStages,
    updateStage,
    deleteStage,
    reset,
    setCurrentTrack,
    resetCurrentTrack,
    showCreator,
    hideCreator,
  }
})
