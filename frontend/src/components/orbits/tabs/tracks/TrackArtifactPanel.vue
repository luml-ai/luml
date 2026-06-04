<template>
  <Dialog
    v-model:visible="isVisible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="TRACK_SETTINGS_DIALOG_PT"
  >
    <template #header>
      <h2 class="dialog-title">
        <Bolt :size="20" color="var(--p-primary-color)" />
        <span>Artifact settings</span>
      </h2>
    </template>
    <div class="form">
      <div class="form-item">
        <label class="label">Name</label>
        <InputText :model-value="entry.artifact_name ?? ''" disabled />
      </div>
      <div class="form-item">
        <label class="label">Stage</label>
        <Select
          v-model="selectedStageId"
          :options="stageOptions"
          option-label="label"
          option-value="value"
          placeholder="Select stage"
        />
      </div>
    </div>
    <template #footer>
      <div>
        <Button
          v-if="canDelete"
          variant="outlined"
          severity="warn"
          :disabled="loading"
          @click="onUnlinkClick"
        >
          unlink artifact
        </Button>
      </div>
      <Button :loading="loading" @click="saveChanges">
        save changes
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { TrackEntry, TrackStage } from '@/lib/api/orbit-tracks/interfaces'
import { computed, ref } from 'vue'
import { Dialog, Button, InputText, Select, useToast, useConfirm } from 'primevue'
import { Bolt } from 'lucide-vue-next'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import {
  unlinkArtifactConfirmOptions,
  forceStageReassignConfirmOptions,
} from '@/lib/primevue/data/confirm'
import { useTracksStore } from '@/stores/tracks'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { TRACK_SETTINGS_DIALOG_PT } from './track.const'
import axios from 'axios'

type Props = {
  entry: TrackEntry
  stages: TrackStage[]
  trackId: string
}

type Emits = {
  'update:visible': [value: boolean]
  'entry-updated': []
  'entry-deleted': []
}

const NONE_VALUE = '__none__'

const props = defineProps<Props>()
const emit = defineEmits<Emits>()

const toast = useToast()
const confirm = useConfirm()
const tracksStore = useTracksStore()
const orbitsStore = useOrbitsStore()

const isVisible = computed({
  get: () => true,
  set: (val: boolean) => emit('update:visible', val),
})

const loading = ref(false)
const selectedStageId = ref<string>(props.entry.stage_id ?? NONE_VALUE)

const canDelete = computed(() =>
  !!orbitsStore.getCurrentOrbitPermissions?.track.includes(PermissionEnum.delete),
)

const stageOptions = computed(() => {
  const options = [{ label: 'None', value: NONE_VALUE }]
  for (const stage of props.stages) {
    options.push({ label: stage.name, value: stage.id })
  }
  return options
})

async function saveChanges() {
  const newStageId = selectedStageId.value === NONE_VALUE ? null : selectedStageId.value
  if (newStageId === props.entry.stage_id) {
    emit('update:visible', false)
    return
  }

  try {
    loading.value = true
    await tracksStore.patchEntry(props.trackId, props.entry.id, { stage_id: newStageId })
    toast.add(simpleSuccessToast('Entry updated'))
    emit('entry-updated')
  } catch (e: unknown) {
    if (axios.isAxiosError(e) && e.response?.status === 409) {
      const detail = e.response.data?.detail ?? 'Stage is already assigned to another entry.'
      confirm.require(
        forceStageReassignConfirmOptions(async () => {
          try {
            loading.value = true
            await tracksStore.patchEntry(
              props.trackId,
              props.entry.id,
              { stage_id: newStageId },
              true,
            )
            toast.add(simpleSuccessToast('Entry updated'))
            emit('entry-updated')
          } catch {
            toast.add(simpleErrorToast('Failed to update entry'))
          } finally {
            loading.value = false
          }
        }, detail),
      )
    } else {
      toast.add(simpleErrorToast('Failed to update entry'))
    }
  } finally {
    loading.value = false
  }
}

function onUnlinkClick() {
  confirm.require(unlinkArtifactConfirmOptions(unlinkEntry))
}

async function unlinkEntry() {
  try {
    loading.value = true
    await tracksStore.deleteEntry(props.trackId, props.entry.id)
    toast.add(simpleSuccessToast('Artifact unlinked'))
    emit('entry-deleted')
  } catch {
    toast.add(simpleErrorToast('Failed to unlink artifact'))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.dialog-title {
  font-weight: 500;
  font-size: 16px;
  text-transform: uppercase;
  display: flex;
  gap: 8px;
  align-items: center;
}
.form {
  display: flex;
  flex-direction: column;
  gap: 20px;
}
.form-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
  align-self: flex-start;
}
</style>
