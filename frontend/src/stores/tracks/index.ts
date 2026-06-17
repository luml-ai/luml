import type {
  Track,
  TrackCreateIn,
  TrackStage,
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
  const creatorVisible = ref(false)
  const editableTrack = ref<{
    id: string
    name: string
    description: string | undefined
    stages: string[]
    lockedStages: string[]
  } | null>(null)
  const trackStages = ref<TrackStage[]>([])

  const requestInfo = computed(() => {
    if (typeof route.params.organizationId !== 'string')
      throw new Error('Current organization not found')
    if (typeof route.params.id !== 'string') throw new Error('Orbit was not found')
    return {
      organizationId: route.params.organizationId,
      orbitId: route.params.id,
    }
  })

  const editorVisible = computed(() => !!editableTrack.value)

  // --- Tracks ---

  function showEditor(track: {
    id: string
    name: string
    description: string | undefined
    stages: string[]
    lockedStages: string[]
  }) {
    editableTrack.value = track
  }

  function hideEditor() {
    editableTrack.value = null
  }

  async function createTrack(payload: TrackCreateIn, requestData?: typeof requestInfo.value) {
    const info = requestData ? requestData : requestInfo.value
    const track = await api.orbitTracks.createTrack(info.organizationId, info.orbitId, payload)
    setTracksList([track, ...tracksList.value])
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

  function getTrackById(trackId: string) {
    const { organizationId, orbitId } = requestInfo.value
    return api.orbitTracks.getTrack(organizationId, orbitId, trackId)
  }

  async function setCurrentTrack(trackId: string) {
    resetTrackStages()
    currentTrack.value = await getTrackById(trackId)
    await listStages(trackId)
  }

  function resetCurrentTrack() {
    currentTrack.value = null
  }

  function reset() {
    tracksList.value = []
    resetCurrentTrack()
  }

  function showCreator() {
    creatorVisible.value = true
  }

  function hideCreator() {
    creatorVisible.value = false
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
    trackStages.value = await api.orbitTracks.listStages(
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

  function resetTrackStages() {
    trackStages.value = []
  }

  return {
    tracksList,
    setTracksList,
    currentTrack,
    creatorVisible,
    requestInfo,
    editableTrack,
    editorVisible,
    showEditor,
    hideEditor,
    createTrack,
    updateTrack,
    deleteTrack,
    reset,
    setCurrentTrack,
    resetCurrentTrack,
    showCreator,
    hideCreator,
    createStage,
    trackStages,
    listStages,
    resetTrackStages,
    updateStage,
    deleteStage,
    getTrackById,
  }
})
