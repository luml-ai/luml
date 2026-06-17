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
        <StageWarning v-if="artifactWithSelectedStage" :artifact="artifactWithSelectedStage" />
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
import type { TrackEntry } from '@/lib/api/orbit-tracks/interfaces'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import { computed, ref, watch, watchEffect } from 'vue'
import { Form, type FormInstance, type FormSubmitEvent } from '@primevue/forms'
import { InputText, Textarea, Button } from 'primevue'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { useToast } from 'primevue'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { Bolt } from 'lucide-vue-next'
import { useConfirm } from 'primevue/useconfirm'
import {
  deleteTrackEntryConfirmOptions,
  patchTrackEntryConfirmOptions,
} from '@/lib/primevue/data/confirm'
import { useTracksStore } from '@/stores/tracks'
import z from 'zod'
import UiDialogRight from '../ui/dialogs/UiDialogRight.vue'
import StageSelect from './StageSelect.vue'
import StageWarning from './StageWarning.vue'

const artifactLinksStore = useArtifactLinksStore()
const toast = useToast()
const confirm = useConfirm()
const tracksStore = useTracksStore()

const formRef = ref<FormInstance>()
const saveLoading = ref(false)
const deleteLoading = ref(false)
const artifactWithSelectedStage = ref<TrackEntry | null>(null)

const initialValues = computed(() => {
  if (!artifactLinksStore.editableEntry) return {}
  return {
    artifact_name: artifactLinksStore.editableEntry.artifact_name,
    artifact_description: artifactLinksStore.editableEntry.artifact_description,
    stage_id: artifactLinksStore.editableEntry.stage_id,
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
  if (artifactWithSelectedStage.value) {
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

async function getArtifactWithSelectedStage(trackId: string, stageId: string) {
  artifactWithSelectedStage.value = null
  try {
    const artifact = await artifactLinksStore.getEntryByStage(trackId, stageId)
    if (artifact.id !== artifactLinksStore.editableEntry?.id) {
      artifactWithSelectedStage.value = artifact
    }
  } catch {
    artifactWithSelectedStage.value = null
  }
}

watch(
  () => artifactLinksStore.editableEntry,
  (entry) => {
    if (!entry) return
  },
)

watchEffect(() => {
  if (!artifactLinksStore.editableEntry) return
  const stageId = formRef.value?.getFieldState('stage_id')?.value
  if (!stageId) {
    artifactWithSelectedStage.value = null
    return
  }
  getArtifactWithSelectedStage(artifactLinksStore.editableEntry.track_id, stageId)
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
</style>
