<template>
  <UiDialogRight :visible="tracksStore.editorVisible" @update:visible="updateVisible">
    <template #header>
      <div class="header-content">
        <Bolt :size="20" color="var(--p-primary-color)" />
        <span>TRACK settings</span>
      </div>
    </template>
    <template #default>
      <Form id="track-edit-form" :initialValues :resolver class="form" @submit="submit">
        <div class="inputs">
          <div class="field">
            <label for="name" class="label">Name</label>
            <InputText id="name" name="name" placeholder="Name your track" fluid />
          </div>
          <div class="field">
            <label for="description" class="label">Description</label>
            <Textarea
              name="description"
              id="description"
              placeholder="Describe your track"
              class="textarea"
              fluid
            ></Textarea>
          </div>
          <div class="field">
            <label for="stages" class="label">Stages</label>
            <UiTagsSelect
              v-model="initialValues.stages"
              id="stages"
              name="stages"
              placeholder="Type to add stages"
              disabled
              :items="['Production', 'Pre-Production', 'Staging']"
              :itemsTooltips="stagesTooltips"
              :disabledValues="tracksStore.editableTrack?.lockedStages ?? []"
            />
          </div>
        </div>
      </Form>
    </template>
    <template #footer>
      <div class="footer-actions">
        <Button
          label="delete track"
          severity="warn"
          variant="outlined"
          :loading="deleteLoading"
          @click="onDeleteClick"
        />
        <Button label="save changes" type="submit" form="track-edit-form" :loading="saveLoading" />
      </div>
    </template>
  </UiDialogRight>
</template>

<script setup lang="ts">
import type { TrackUpdateIn } from '@/lib/api/orbit-tracks/interfaces.js'
import { Button, InputText, Textarea, useToast, useConfirm } from 'primevue'
import { useTracksStore } from '@/stores/tracks'
import { Bolt } from 'lucide-vue-next'
import { computed, ref, watch } from 'vue'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { getErrorMessage } from '@/helpers/helpers'
import { deleteTrackConfirmOptions } from '@/lib/primevue/data/confirm'
import z from 'zod'
import UiDialogRight from '../ui/dialogs/UiDialogRight.vue'
import UiTagsSelect from '../ui/UiTagsSelect.vue'

const tracksStore = useTracksStore()
const toast = useToast()
const confirm = useConfirm()

const initialValues = ref<{ name: string; description: string; stages: string[] }>({
  name: '',
  description: '',
  stages: [],
})

const deleteLoading = ref(false)
const saveLoading = ref(false)

const resolver = zodResolver(
  z.object({
    name: z.string().min(1).max(100),
    description: z.string().max(255).optional(),
    stages: z.array(z.string().min(1).max(100)).min(1),
  }),
)

const stagesTooltips = computed(() => {
  if (!tracksStore.editableTrack) return {}
  return tracksStore.editableTrack.lockedStages.reduce(
    (acc, stage) => {
      acc[stage] = `This stage was linked to an artifact. To remove it, unlink the stage.`
      return acc
    },
    {} as Record<string, string>,
  )
})

function updateVisible(visible: boolean) {
  if (!visible) tracksStore.hideEditor()
}

function onDeleteClick() {
  confirm.require(deleteTrackConfirmOptions(deleteTrack))
}

async function deleteTrack() {
  try {
    if (!tracksStore.editableTrack?.id) throw new Error('Track ID is required')
    deleteLoading.value = true
    await tracksStore.deleteTrack(tracksStore.editableTrack.id)
    toast.add(simpleSuccessToast('Track has been successfully deleted'))
    tracksStore.hideEditor()
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to delete track')))
  } finally {
    deleteLoading.value = false
  }
}

async function submit({ values, valid, reset }: FormSubmitEvent) {
  if (!valid) return
  try {
    saveLoading.value = true
    const { name, description } = values
    const payload: TrackUpdateIn = {
      name,
      description,
    }
    if (!tracksStore.editableTrack?.id) throw new Error('Track ID is required')
    await tracksStore.updateTrack(tracksStore.editableTrack.id, payload)
    reset()
    tracksStore.hideEditor()
    toast.add(simpleSuccessToast('Track has been successfully updated'))
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to update track')))
  } finally {
    saveLoading.value = false
  }
}

watch(
  () => tracksStore.editableTrack,
  (track) => {
    initialValues.value.name = track?.name ?? ''
    initialValues.value.description = track?.description ?? ''
    initialValues.value.stages = track?.lockedStages ?? []
  },
)
</script>

<style scoped>
.header-content {
  display: flex;
  align-items: center;
  gap: 8px;
}
.footer-actions {
  width: 100%;
  display: flex;
  gap: 10px;
  justify-content: space-between;
}
.form {
}
.inputs {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 28px;
}
.field {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 7px;
}
.label {
}
.required {
}
.textarea {
  height: 72px;
  resize: none;
}
</style>
