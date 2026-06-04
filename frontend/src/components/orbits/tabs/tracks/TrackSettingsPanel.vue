<template>
  <Dialog
    v-model:visible="visible"
    position="topright"
    :draggable="false"
    style="margin-top: 80px; height: 86%; width: 420px"
    :pt="TRACK_SETTINGS_DIALOG_PT"
  >
    <template #header>
      <h2 class="dialog-title">
        <Bolt :size="20" color="var(--p-primary-color)" />
        <span>Track settings</span>
      </h2>
    </template>
    <Form
      id="track-edit-form"
      :initialValues
      :resolver="trackEditorResolver"
      class="form"
      @submit="saveChanges"
    >
      <div class="form-item">
        <label for="name" class="label">Name</label>
        <InputText v-model="initialValues.name" name="name" id="name" />
      </div>
      <div class="form-item">
        <label for="description" class="label">Description</label>
        <Textarea
          v-model="initialValues.description"
          name="description"
          id="description"
          placeholder="Describe your track"
          style="height: 72px; resize: none"
        ></Textarea>
      </div>
      <div class="form-item">
        <label for="tags" class="label">Tags</label>
        <AutoComplete
          v-model="initialValues.tags"
          id="tags"
          name="tags"
          placeholder="Type to add tags"
          fluid
          multiple
          :suggestions="tagSuggestions"
          @complete="searchTags"
        ></AutoComplete>
      </div>
      <div class="form-item">
        <label class="label">Stages</label>
        <div class="stages-chips">
          <Tag
            v-for="stage in currentStages"
            :key="stage.id"
            :style="getStageBadgeStyle(stage.name)"
            class="stage-chip"
          >
            <span>{{ stage.name }}</span>
            <button
              v-if="canUpdate"
              v-tooltip="stageEntryUsage[stage.id] ? 'This stage was linked to an artifact. To remove it, unlink the stage.' : undefined"
              class="stage-remove"
              type="button"
              @click="removeStage(stage)"
            >
              <X :size="10" />
            </button>
          </Tag>
          <Tag
            v-for="name in newStageNames"
            :key="name"
            class="stage-chip stage-chip--new"
          >
            <span>{{ name }}</span>
            <button
              class="stage-remove"
              type="button"
              @click="removeNewStage(name)"
            >
              <X :size="10" />
            </button>
          </Tag>
        </div>
        <InputText
          v-if="canUpdate"
          v-model="newStageInput"
          placeholder="Type to add stages"
          @keydown.enter.prevent="addNewStage"
        />
      </div>
    </Form>
    <template #footer>
      <div>
        <Button
          v-if="canDelete"
          variant="outlined"
          severity="warn"
          :disabled="loading"
          @click="onDeleteClick"
        >
          delete track
        </Button>
      </div>
      <Button
        v-if="canUpdate"
        type="submit"
        :loading="loading"
        form="track-edit-form"
      >
        save changes
      </Button>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import type { Track, TrackStage } from '@/lib/api/orbit-tracks/interfaces'
import { computed, ref, watch } from 'vue'
import {
  type AutoCompleteCompleteEvent,
  Dialog,
  Button,
  InputText,
  Textarea,
  AutoComplete,
  Tag,
  useToast,
  useConfirm,
} from 'primevue'
import { Bolt, X } from 'lucide-vue-next'
import { Form } from '@primevue/forms'
import { api } from '@/lib/api'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { deleteTrackConfirmOptions } from '@/lib/primevue/data/confirm'
import { useTracksStore } from '@/stores/tracks'
import { useOrbitsStore } from '@/stores/orbits'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { trackEditorResolver } from '@/utils/forms/resolvers'
import { TRACK_SETTINGS_DIALOG_PT } from './track.const'
import { getStageBadgeStyle } from './stage-colors'

type Props = {
  data: Track
}

const props = defineProps<Props>()

const visible = defineModel<boolean>('visible')

const toast = useToast()
const confirm = useConfirm()
const tracksStore = useTracksStore()
const orbitsStore = useOrbitsStore()

const initialValues = ref({
  name: props.data.name,
  description: props.data.description ?? '',
  tags: Array.isArray(props.data.tags) ? [...props.data.tags] : [],
})
const loading = ref(false)
const currentStages = ref<TrackStage[]>([])
const removedStageIds = ref<string[]>([])
const newStageNames = ref<string[]>([])
const newStageInput = ref('')
const stageEntryUsage = ref<Record<string, boolean>>({})

const canUpdate = computed(() =>
  !!orbitsStore.getCurrentOrbitPermissions?.track.includes(PermissionEnum.update),
)
const canDelete = computed(() =>
  !!orbitsStore.getCurrentOrbitPermissions?.track.includes(PermissionEnum.delete),
)

const existingTags = computed(() => {
  const tagsSet = tracksStore.tracksList.reduce((acc: Set<string>, item) => {
    if (!Array.isArray(item.tags)) return acc
    item.tags.forEach((tag) => acc.add(tag))
    return acc
  }, new Set<string>())
  return Array.from(tagsSet)
})
const tagSuggestions = ref<string[]>([])

function searchTags(event: AutoCompleteCompleteEvent) {
  tagSuggestions.value = [
    event.query,
    ...existingTags.value.filter((tag) => tag.toLowerCase().includes(event.query.toLowerCase())),
  ]
}

async function loadStages() {
  try {
    const stagesList = await tracksStore.listStages(props.data.id)
    currentStages.value = stagesList

    const { organizationId, orbitId } = tracksStore.requestInfo
    const result = await api.orbitTracks.listEntries(organizationId, orbitId, props.data.id, {
      cursor: null,
      limit: 100,
    })
    const usedStageIds = new Set(
      result.items.filter((e) => e.stage_id).map((e) => e.stage_id as string),
    )
    const usage: Record<string, boolean> = {}
    for (const stage of stagesList) {
      usage[stage.id] = usedStageIds.has(stage.id)
    }
    stageEntryUsage.value = usage
  } catch {
    toast.add(simpleErrorToast('Failed to load stages'))
  }
}

function removeStage(stage: TrackStage) {
  if (stageEntryUsage.value[stage.id]) {
    return
  }
  currentStages.value = currentStages.value.filter((s) => s.id !== stage.id)
  removedStageIds.value.push(stage.id)
}

function removeNewStage(name: string) {
  newStageNames.value = newStageNames.value.filter((n) => n !== name)
}

function addNewStage() {
  const name = newStageInput.value.trim()
  if (!name) return
  const alreadyExists = currentStages.value.some(
    (s) => s.name.toLowerCase() === name.toLowerCase(),
  )
  const alreadyNew = newStageNames.value.some(
    (n) => n.toLowerCase() === name.toLowerCase(),
  )
  if (alreadyExists || alreadyNew) {
    toast.add(simpleErrorToast('Stage already exists'))
    return
  }
  newStageNames.value.push(name)
  newStageInput.value = ''
}

async function saveChanges() {
  try {
    loading.value = true

    await tracksStore.updateTrack(props.data.id, {
      name: initialValues.value.name,
      description: initialValues.value.description || null,
      tags: initialValues.value.tags,
    })

    for (const name of newStageNames.value) {
      await tracksStore.createStage(props.data.id, { name })
    }

    for (const stageId of removedStageIds.value) {
      await tracksStore.deleteStage(props.data.id, stageId)
    }

    toast.add(simpleSuccessToast('Track successfully updated'))
    visible.value = false
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || 'Failed to update track'))
  } finally {
    loading.value = false
  }
}

function onDeleteClick() {
  confirm.require(deleteTrackConfirmOptions(deleteTrack))
}

async function deleteTrack() {
  try {
    loading.value = true
    await tracksStore.deleteTrack(props.data.id)
    toast.add(simpleSuccessToast(`Track "${props.data.name}" was deleted.`))
    visible.value = false
  } catch {
    toast.add(simpleErrorToast('Failed to delete track'))
  } finally {
    loading.value = false
  }
}

watch(visible, (val) => {
  if (val) {
    initialValues.value = {
      name: props.data.name,
      description: props.data.description ?? '',
      tags: Array.isArray(props.data.tags) ? [...props.data.tags] : [],
    }
    removedStageIds.value = []
    newStageNames.value = []
    newStageInput.value = ''
    loadStages()
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
.stages-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 4px;
}
.stage-chip {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-weight: 400;
}
.stage-chip--new {
  border: 1px dashed var(--p-content-border-color);
}
.stage-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  cursor: pointer;
  padding: 0;
  color: inherit;
  opacity: 0.7;
}
.stage-remove:hover {
  opacity: 1;
}
</style>
