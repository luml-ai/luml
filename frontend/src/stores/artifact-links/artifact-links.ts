import { defineStore } from 'pinia'
import { computed, ref } from 'vue'
import type {
  TrackEntry,
  TrackEntryCreateIn,
  TrackEntryUpdateIn,
} from '@/lib/api/orbit-tracks/interfaces'
import { useRoute } from 'vue-router'
import { api } from '@/lib/api'

export const useArtifactLinksStore = defineStore('artifact-links', () => {
  const route = useRoute()

  const entriesList = ref<TrackEntry[]>([])
  const creatorVisible = ref(false)
  const selectedEntries = ref<TrackEntry[]>([])
  const editableEntry = ref<TrackEntry | null>(null)

  const requestInfo = computed(() => {
    if (typeof route.params.organizationId !== 'string' || typeof route.params.id !== 'string')
      return null
    return {
      organizationId: route.params.organizationId,
      orbitId: route.params.id,
    }
  })

  const stagingEntries = computed(() => {
    return entriesList.value.filter((e) => e.stage_name === 'Staging')
  })

  function showCreator() {
    creatorVisible.value = true
  }

  function hideCreator() {
    creatorVisible.value = false
  }

  function addSelectedEntry(entry: TrackEntry) {
    selectedEntries.value.push(entry)
  }

  function removeSelectedEntry(entry: TrackEntry) {
    selectedEntries.value = selectedEntries.value.filter((e) => e.id !== entry.id)
  }

  function clearSelectedEntries() {
    selectedEntries.value = []
  }

  async function addEntry(trackId: string, payload: TrackEntryCreateIn) {
    if (!requestInfo.value) throw new Error('Request info not found')
    const newEntry = await api.orbitTracks.addEntry(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      payload,
    )
    entriesList.value = [newEntry, ...entriesList.value]
  }

  async function patchEntry(
    trackId: string,
    entryId: string,
    payload: TrackEntryUpdateIn,
    force?: boolean,
  ) {
    if (!requestInfo.value) throw new Error('Request info not found')
    const updatedEntry = await api.orbitTracks.patchEntry(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      entryId,
      payload,
      force,
    )

    entriesList.value = entriesList.value.map((old) => {
      if (old.id === entryId) {
        return updatedEntry
      } else if (updatedEntry.stage_name === 'Staging' && old.stage_name === 'Staging') {
        return { ...old, stage_id: null, stage_name: null }
      } else {
        return old
      }
    })
  }

  async function deleteEntry(trackId: string, entryId: string) {
    if (!requestInfo.value) throw new Error('Request info not found')
    await api.orbitTracks.deleteEntry(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      entryId,
    )
    entriesList.value = entriesList.value.filter((e) => e.id !== entryId)
  }

  async function deleteEntries(trackId: string, entryIds: string[]) {
    if (!requestInfo.value) throw new Error('Request info not found')
    await api.orbitTracks.deleteEntries(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      entryIds,
    )
    entriesList.value = entriesList.value.filter((e) => !entryIds.includes(e.id))
  }

  function showEditor(entry: TrackEntry) {
    editableEntry.value = entry
  }

  function hideEditor() {
    editableEntry.value = null
  }

  function setEntriesList(entries: TrackEntry[]) {
    entriesList.value = entries
  }

  async function getEntryByStage(trackId: string, stageId: string) {
    if (!requestInfo.value) throw new Error('Request info not found')
    return await api.orbitTracks.getEntryByStage(
      requestInfo.value.organizationId,
      requestInfo.value.orbitId,
      trackId,
      stageId,
    )
  }

  return {
    creatorVisible,
    showCreator,
    hideCreator,
    selectedEntries,
    addSelectedEntry,
    removeSelectedEntry,
    clearSelectedEntries,
    addEntry,
    patchEntry,
    deleteEntry,
    deleteEntries,
    editableEntry,
    showEditor,
    hideEditor,
    entriesList,
    setEntriesList,
    stagingEntries,
    getEntryByStage,
  }
})
