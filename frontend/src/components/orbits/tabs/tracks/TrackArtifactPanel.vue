<template>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="dialogPT"
  >
    <template #header>
      <h2 class="dialog-title">
        <LinkIcon :size="20" color="var(--p-primary-color)" />
        <span>Entry details</span>
      </h2>
    </template>

    <div v-if="entry" class="form">
      <div class="form-item">
        <label class="label">Artifact</label>
        <InputText :model-value="entry.artifact_id" disabled />
      </div>
      <div class="form-item">
        <label class="label">Version</label>
        <InputText :model-value="`v${entry.version}`" disabled />
      </div>
      <div class="form-item">
        <label for="entry-stage" class="label">Stage</label>
        <Select
          v-model="selectedStageId"
          :options="stageOptions"
          option-label="label"
          option-value="value"
          placeholder="Select a stage"
          id="entry-stage"
        />
      </div>
    </div>

    <template #footer>
      <div>
        <Button
          v-if="canDelete"
          variant="outlined"
          severity="warn"
          :disabled="saving"
          @click="onUnlinkClick"
        >
          unlink artifact
        </Button>
      </div>
      <Button :loading="saving" @click="saveChanges">
        save changes
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { ITrackArtifact, ITrackStage, ITrackStageConflict } from '@/lib/api/orbit-tracks/interfaces'
import { computed, ref, watch } from 'vue'
import {
  type DialogPassThroughOptions,
  Dialog,
  Button,
  InputText,
  Select,
  useToast,
  useConfirm,
} from 'primevue'
import { Link as LinkIcon } from 'lucide-vue-next'
import { useTracksStore } from '@/stores/tracks'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { unlinkArtifactConfirmOptions } from '@/lib/primevue/data/confirm'
import { PermissionEnum } from '@/lib/api/api.interfaces'

type Props = {
  entry: ITrackArtifact | null
  stages: ITrackStage[]
  trackId: string
}

type Emits = {
  (e: 'entryUpdated', entry: ITrackArtifact): void
  (e: 'entryDeleted', entryId: string): void
}

const NONE_VALUE = '__none__'

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
const visible = defineModel<boolean>('visible')

const dialogPT: DialogPassThroughOptions = {
  footer: {
    style: 'display: flex; justify-content: space-between; width: 100%; margin-top: auto;',
  },
}

const toast = useToast()
const confirm = useConfirm()
const tracksStore = useTracksStore()
const orbitsStore = useOrbitsStore()

const selectedStageId = ref<string>(NONE_VALUE)
const saving = ref(false)

const canDelete = computed(() => {
  return !!orbitsStore.getCurrentOrbitPermissions?.track?.includes(PermissionEnum.delete)
})

const stageOptions = computed(() => {
  const options = [{ label: 'None', value: NONE_VALUE }]
  for (const stage of props.stages) {
    options.push({ label: stage.name, value: stage.id })
  }
  return options
})

function onUnlinkClick() {
  confirm.require(unlinkArtifactConfirmOptions(unlinkArtifact))
}

async function unlinkArtifact() {
  if (!props.entry) return
  try {
    saving.value = true
    await tracksStore.deleteEntry(props.trackId, props.entry.id)
    toast.add(simpleSuccessToast('Artifact unlinked'))
    emit('entryDeleted', props.entry.id)
    visible.value = false
  } catch {
    toast.add(simpleErrorToast('Failed to unlink artifact'))
  } finally {
    saving.value = false
  }
}

async function saveChanges() {
  if (!props.entry) return
  const stageId = selectedStageId.value === NONE_VALUE ? null : selectedStageId.value

  try {
    saving.value = true
    const response = await tracksStore.patchEntry(
      props.trackId,
      props.entry.id,
      { stage_id: stageId },
    )
    toast.add(simpleSuccessToast('Entry updated'))
    emit('entryUpdated', response.entry)
    visible.value = false
  } catch (e: any) {
    if (e?.response?.status === 409 && e?.response?.data) {
      const conflict = e.response.data as ITrackStageConflict
      confirm.require({
        message: `Stage '${conflict.stage_name}' is already assigned to v${conflict.held_by_version}. Move it here?`,
        header: 'Stage conflict',
        rejectProps: { label: 'cancel' },
        acceptProps: { label: 'move stage' },
        accept: () => forceAssignStage(stageId),
      })
    } else {
      toast.add(simpleErrorToast('Failed to update entry'))
    }
  } finally {
    saving.value = false
  }
}

async function forceAssignStage(stageId: string | null) {
  if (!props.entry) return
  try {
    saving.value = true
    const response = await tracksStore.patchEntry(
      props.trackId,
      props.entry.id,
      { stage_id: stageId },
      true,
    )
    toast.add(simpleSuccessToast('Entry updated'))
    emit('entryUpdated', response.entry)
    visible.value = false
  } catch {
    toast.add(simpleErrorToast('Failed to update entry'))
  } finally {
    saving.value = false
  }
}

watch(visible, (val) => {
  if (val && props.entry) {
    selectedStageId.value = props.entry.stage?.id ?? NONE_VALUE
  }
})
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
