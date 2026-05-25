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
        <Settings :size="20" color="var(--p-primary-color)" />
        <span>Track settings</span>
      </h2>
    </template>

    <div class="form">
      <div class="form-item">
        <label for="track-name" class="label">Name</label>
        <InputText v-model="formData.name" id="track-name" />
      </div>
      <div class="form-item">
        <label for="track-description" class="label">Description</label>
        <Textarea
          v-model="formData.description"
          id="track-description"
          placeholder="Describe your track"
          style="height: 72px; resize: none"
        />
      </div>
      <div class="form-item">
        <label for="track-tags" class="label">Tags</label>
        <AutoComplete
          v-model="formData.tags"
          id="track-tags"
          placeholder="Type to add tags"
          fluid
          multiple
          :suggestions="tagSuggestions"
          @complete="onTagSearch"
        />
      </div>
      <div class="form-item">
        <label class="label">Stages</label>
        <div class="stages-list">
          <div v-for="stage in localStages" :key="stage.id" class="stage-chip">
            <span>{{ stage.name }}</span>
            <button
              v-if="!stage.inUse"
              class="stage-remove"
              @click="removeStage(stage)"
            >
              &times;
            </button>
            <span
              v-else
              v-tooltip="'This stage was linked to an artifact. To remove it, unlink the stage.'"
              class="stage-remove stage-remove--disabled"
            >
              &times;
            </span>
          </div>
        </div>
        <div class="stage-add">
          <InputText
            v-model="newStageName"
            size="small"
            placeholder="Add a new stage"
            @keydown.enter="addLocalStage"
          />
          <Button
            size="small"
            variant="text"
            :disabled="!newStageName.trim()"
            @click="addLocalStage"
          >
            Add
          </Button>
        </div>
      </div>
    </div>

    <template #footer>
      <div>
        <Button
          v-if="canDelete"
          variant="outlined"
          severity="warn"
          :disabled="saving"
          @click="onDeleteClick"
        >
          delete track
        </Button>
      </div>
      <Button :loading="saving" @click="saveChanges">
        save changes
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { ITrack, ITrackStage } from '@/lib/api/orbit-tracks/interfaces'
import type { AutoCompleteCompleteEvent } from 'primevue'
import { computed, ref, watch } from 'vue'
import {
  type DialogPassThroughOptions,
  Dialog,
  Button,
  InputText,
  Textarea,
  AutoComplete,
  useToast,
  useConfirm,
} from 'primevue'
import { Settings } from 'lucide-vue-next'
import { useTracksStore } from '@/stores/tracks'
import { useOrbitsStore } from '@/stores/orbits'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteTrackConfirmOptions } from '@/lib/primevue/data/confirm'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { getErrorMessage } from '@/helpers/helpers'

interface LocalStage {
  id: string
  name: string
  isNew: boolean
  inUse: boolean
}

type Props = {
  data: ITrack
  stages: ITrackStage[]
  stagesInUse: Set<string>
}

type Emits = {
  (e: 'trackUpdated', track: ITrack): void
  (e: 'trackDeleted'): void
  (e: 'stagesChanged'): void
}

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

const formData = ref({
  name: '',
  description: '' as string | null,
  tags: [] as string[],
})
const localStages = ref<LocalStage[]>([])
const removedStageIds = ref<string[]>([])
const newStageName = ref('')
const saving = ref(false)
const tagSuggestions = ref<string[]>([])

const canDelete = computed(() => {
  return !!orbitsStore.getCurrentOrbitPermissions?.track?.includes(PermissionEnum.delete)
})

function onTagSearch(event: AutoCompleteCompleteEvent) {
  tagSuggestions.value = event.query ? [event.query] : []
}

function addLocalStage() {
  const name = newStageName.value.trim()
  if (!name) return
  if (localStages.value.some((s) => s.name === name)) return

  localStages.value.push({
    id: `new-${Date.now()}`,
    name,
    isNew: true,
    inUse: false,
  })
  newStageName.value = ''
}

function removeStage(stage: LocalStage) {
  if (stage.inUse) return
  localStages.value = localStages.value.filter((s) => s.id !== stage.id)
  if (!stage.isNew) {
    removedStageIds.value.push(stage.id)
  }
}

function onDeleteClick() {
  confirm.require(deleteTrackConfirmOptions(deleteTrack))
}

async function deleteTrack() {
  try {
    saving.value = true
    await tracksStore.deleteTrack(props.data.id)
    toast.add(simpleSuccessToast('Track deleted'))
    visible.value = false
    emit('trackDeleted')
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to delete track')))
  } finally {
    saving.value = false
  }
}

async function saveChanges() {
  try {
    saving.value = true

    const updatedTrack = await tracksStore.updateTrack(props.data.id, {
      name: formData.value.name,
      description: formData.value.description,
      tags: formData.value.tags,
    })

    for (const stageId of removedStageIds.value) {
      await tracksStore.deleteStage(props.data.id, stageId, true)
    }

    for (const stage of localStages.value) {
      if (stage.isNew) {
        await tracksStore.createStage(props.data.id, { name: stage.name })
      }
    }

    toast.add(simpleSuccessToast('Track updated'))
    visible.value = false
    emit('trackUpdated', updatedTrack)
    emit('stagesChanged')
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to update track')))
  } finally {
    saving.value = false
  }
}

watch(visible, (val) => {
  if (val) {
    formData.value = {
      name: props.data.name,
      description: props.data.description ?? '',
      tags: [...(props.data.tags || [])],
    }
    localStages.value = props.stages.map((s) => ({
      id: s.id,
      name: s.name,
      isNew: false,
      inUse: props.stagesInUse.has(s.id),
    }))
    removedStageIds.value = []
    newStageName.value = ''
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

.stages-list {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.stage-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 4px;
  font-size: 12px;
  background-color: var(--p-tag-primary-background);
  color: var(--p-tag-primary-color);
}

.stage-remove {
  background: none;
  border: none;
  cursor: pointer;
  font-size: 14px;
  line-height: 1;
  padding: 0 2px;
  color: inherit;
}

.stage-remove--disabled {
  cursor: not-allowed;
  opacity: 0.5;
}

.stage-add {
  display: flex;
  gap: 8px;
  align-items: center;
}
</style>
