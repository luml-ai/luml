<template>
  <Dialog
    v-model:visible="visible"
    header="Link to TRACK"
    modal
    :draggable="false"
    :pt="TRACK_CREATOR_DIALOG_PT"
  >
    <div class="inputs">
      <div class="field">
        <label for="track" class="label required">Track</label>
        <Select
          v-model="selectedTrackId"
          id="track"
          name="track"
          placeholder="Select track"
          fluid
          filter
          :options="selectableOptions"
          option-label="name"
          option-value="id"
          option-disabled="disabled"
          :virtualScrollerOptions="trackScrollerOptions"
          @filter="onTrackFilter"
        />
      </div>
    </div>

    <Button
      type="button"
      fluid
      rounded
      :loading="loading"
      :disabled="!selectedTrackId"
      @click="onConfirm"
    >
      Confirm
    </Button>
  </Dialog>
</template>

<script setup lang="ts">
import type { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { SelectFilterEvent } from 'primevue'
import { Dialog, Button, Select, useToast } from 'primevue'
import { ref, watch, computed } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { useTracksStore } from '@/stores/tracks'
import { useTracksList } from '@/hooks/useTracksList'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { TRACK_CREATOR_DIALOG_PT } from './track.const'

type Props = {
  artifactId: string
  artifactType: ArtifactTypeEnum
  existingTrackIds: Set<string>
}

const props = defineProps<Props>()

const emit = defineEmits<{
  (e: 'entry-added'): void
}>()

const visible = defineModel<boolean>('visible')
const tracksStore = useTracksStore()
const toast = useToast()

const selectedTrackId = ref<string | null>(null)
const loading = ref(false)

const {
  setRequestInfo,
  getInitialPage,
  tracksList,
  reset: resetTracks,
  onLazyLoad,
  setSearchQuery,
  setTypesQuery,
} = useTracksList(20, false)

const selectableOptions = computed(() => {
  return tracksList.value.map((track) => ({
    ...track,
    disabled: props.existingTrackIds.has(track.id),
  }))
})

const trackScrollerOptions = computed(() => {
  if (tracksList.value.length < 10) return undefined
  return { lazy: true, onLazyLoad, itemSize: 38 }
})

const debouncedTrackFilter = useDebounceFn(async () => {
  try {
    resetTracks()
    setRequestInfo({
      organizationId: tracksStore.requestInfo.organizationId,
      orbitId: tracksStore.requestInfo.orbitId,
    })
    await getInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load tracks')))
  }
}, 500)

function onTrackFilter(event: SelectFilterEvent) {
  setSearchQuery(event.value)
  debouncedTrackFilter()
}

async function onConfirm() {
  if (!selectedTrackId.value) return
  try {
    loading.value = true
    await tracksStore.addEntry(selectedTrackId.value, { artifact_id: props.artifactId })
    toast.add(simpleSuccessToast('Artifact linked to track'))
    visible.value = false
    emit('entry-added')
  } catch (e: any) {
    toast.add(
      simpleErrorToast(e?.response?.data?.detail || getErrorMessage(e, 'Failed to link artifact')),
    )
  } finally {
    loading.value = false
  }
}

watch(visible, async (value) => {
  if (value) {
    selectedTrackId.value = null
    resetTracks()
    try {
      setTypesQuery([props.artifactType])
      setRequestInfo({
        organizationId: tracksStore.requestInfo.organizationId,
        orbitId: tracksStore.requestInfo.orbitId,
      })
      await getInitialPage()
    } catch (e) {
      toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load tracks')))
    }
  }
})
</script>

<style scoped>
.inputs {
  margin-bottom: 28px;
  display: flex;
  flex-direction: column;
  gap: 16px;
}
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}
.label {
  align-self: flex-start;
  font-size: 14px;
}
</style>
