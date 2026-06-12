<template>
  <UiDialogRight :visible="!!artifactLinksStore.editableEntry" @update:visible="onVisibleChange">
    <template #header>
      <div class="dialog-title">
        <Bolt :size="20" color="var(--p-primary-color)" />
        <span>ARTIFACT settings</span>
      </div>
    </template>
    <template #default>
      <Form
        ref="formRef"
        id="link-artifact-edit-form"
        :initialValues
        :resolver
        class="form"
        @submit="onSubmit"
      >
        <div class="field">
          <label for="name" class="label">Name</label>
          <InputText id="name" name="artifact_name" placeholder="Name your track" fluid disabled />
        </div>
        <div class="field">
          <label for="description" class="label">Description</label>
          <Textarea
            name="artifact_description"
            id="description"
            placeholder="-"
            class="textarea"
            fluid
            disabled
          ></Textarea>
        </div>
        <StageSelect :options="tracksStore.trackStages" />
        <div v-if="stageWarning" class="message">
          <TriangleAlert :size="16" class="message-icon" />
          <div class="message-content">
            <h3 class="message-title">
              {{ stageWarning.title }}
            </h3>
            <p class="message-description">
              {{ stageWarning.description }}
            </p>
          </div>
        </div>
      </Form>
    </template>
    <template #footer>
      <div class="footer-actions">
        <Button
          label="unlink artifact"
          severity="warn"
          variant="outlined"
          :loading="deleteLoading"
          @click="onDeleteClick"
        />
        <Button
          label="save changes"
          type="submit"
          form="link-artifact-edit-form"
          :loading="saveLoading"
        />
      </div>
    </template>
  </UiDialogRight>
</template>

<script setup lang="ts">
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import { computed, ref, watch } from 'vue'
import { Form, type FormInstance, type FormSubmitEvent } from '@primevue/forms'
import { InputText, Textarea, Button } from 'primevue'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { useToast } from 'primevue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { Bolt, TriangleAlert } from 'lucide-vue-next'
import { useConfirm } from 'primevue/useconfirm'
import {
  deleteTrackEntryConfirmOptions,
  patchTrackEntryConfirmOptions,
} from '@/lib/primevue/data/confirm'
import { useTracksStore } from '@/stores/tracks'
import z from 'zod'
import UiDialogRight from '../ui/dialogs/UiDialogRight.vue'
import StageSelect from './StageSelect.vue'
import type { TrackEntry } from '@/lib/api/orbit-tracks/interfaces'

const artifactLinksStore = useArtifactLinksStore()
const toast = useToast()
const confirm = useConfirm()
const tracksStore = useTracksStore()

const formRef = ref<FormInstance>()
const saveLoading = ref(false)
const deleteLoading = ref(false)
const stagingTrackArtifact = ref<TrackEntry | null>(null)

const initialValues = computed(() => {
  if (!artifactLinksStore.editableEntry) return {}
  return {
    artifact_name: artifactLinksStore.editableEntry.artifact_name,
    artifact_description: artifactLinksStore.editableEntry.artifact_description,
    stage_id: artifactLinksStore.editableEntry.stage_id,
  }
})

const stageWarning = computed(() => {
  if (!stagingTrackArtifact.value) return null
  if (stagingTrackArtifact.value.track_id !== artifactLinksStore.editableEntry?.track_id)
    return null
  const isSameArtifact = stagingTrackArtifact.value.id === artifactLinksStore.editableEntry?.id
  if (isSameArtifact) return null
  return {
    title: 'This stage is already in use by another artifact.',
    description: `Once confirmed, the artifact ${stagingTrackArtifact.value.artifact_name} will be unlinked from this stage.`,
  }
})

const resolver = zodResolver(
  z.object({
    artifact_name: z.string().min(1).max(100),
    artifact_description: z.string().max(255).optional(),
    stage_id: z.string().min(1).max(100).optional(),
  }),
)

function onVisibleChange(visible: boolean) {
  if (visible) return
  else artifactLinksStore.hideEditor()
}

async function onSubmit({ values, valid }: FormSubmitEvent) {
  if (!valid) return
  const { stage_id } = values
  if (stageWarning.value) {
    confirm.require(patchTrackEntryConfirmOptions(() => patchEntry(stage_id, true)))
  } else {
    await patchEntry(stage_id, false)
  }
}

async function patchEntry(stageId: string, force: boolean) {
  if (!artifactLinksStore.editableEntry) return
  try {
    saveLoading.value = true
    await artifactLinksStore.patchEntry(
      artifactLinksStore.editableEntry.track_id,
      artifactLinksStore.editableEntry.id,
      { stage_id: stageId },
      force,
    )
    toast.add(simpleSuccessToast('Artifact updated'))
    artifactLinksStore.clearSelectedEntries()
    artifactLinksStore.hideEditor()
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to update artifact')))
  } finally {
    saveLoading.value = false
  }
}

function onDeleteClick() {
  confirm.require(deleteTrackEntryConfirmOptions(deleteEntry, 1))
}

async function deleteEntry() {
  if (!artifactLinksStore.editableEntry) return
  try {
    deleteLoading.value = true
    await artifactLinksStore.deleteEntry(
      artifactLinksStore.editableEntry.track_id,
      artifactLinksStore.editableEntry.id,
    )
    toast.add(
      simpleSuccessToast(
        `${artifactLinksStore.editableEntry.artifact_name} has been unlinked from the track successfully.`,
      ),
    )
    artifactLinksStore.clearSelectedEntries()
    artifactLinksStore.hideEditor()
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to unlink artifact')))
  } finally {
    deleteLoading.value = false
  }
}

async function getStagingTrackArtifact(trackId: string) {
  try {
    await tracksStore.listStages(trackId)
    const stagingStage = tracksStore.trackStages.find(
      (stage) => stage.name.toLowerCase() === 'staging',
    )
    if (!stagingStage) return
    const artifact = await artifactLinksStore.getEntryByStage(trackId, stagingStage.id)
    if (artifact) {
      stagingTrackArtifact.value = artifact
    }
  } catch {
    stagingTrackArtifact.value = null
  }
}

watch(
  () => artifactLinksStore.editableEntry,
  (entry) => {
    if (!entry) return
  },
)

watch(
  () => artifactLinksStore.editableEntry,
  (entry) => {
    if (!entry) return
    stagingTrackArtifact.value = null
    getStagingTrackArtifact(entry.track_id)
  },
)
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
.field {
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.label {
  font-weight: 500;
  align-self: flex-start;
}
.textarea {
  height: 71px;
  resize: none;
}
.footer-actions {
  width: 100%;
  display: flex;
  gap: 12px;
  justify-content: space-between;
}
.placeholder {
  color: var(--p-text-muted-color);
}
.message {
  padding: var(--p-toast-content-padding);
  background-color: var(--p-toast-warn-background);
  border-radius: var(--p-toast-border-radius);
  border: var(--p-toast-border-width) solid var(--p-toast-warn-border-color);
  color: var(--p-toast-warn-color);
  display: flex;
  gap: var(--p-toast-content-gap);
}
.message-icon {
  flex: 0 0 auto;
}
.message-content {
  flex: 1 1 auto;
  display: flex;
  flex-direction: column;
  gap: var(--p-toast-text-gap);
}
.message-title {
  font-weight: var(--p-toast-summary-font-weight);
  font-size: var(--p-toast-summary-font-size);
}
.message-description {
  font-weight: var(--p-toast-detail-font-weight);
  font-size: var(--p-toast-detail-font-size);
  color: var(--p-toast-warn-detail-color);
}
</style>
