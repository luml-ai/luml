<template>
  <Dialog
    :visible="tracksStore.creatorVisible"
    header="Create a new TRACK"
    modal
    :draggable="false"
    :pt="TRACKS_CREATOR_DIALOG_PT"
    @update:visible="onVisibleChange"
  >
    <Form v-slot="$form" :initial-values="initialValues" :resolver="resolver" @submit="onSubmit">
      <div class="inputs">
        <div class="field">
          <label for="name" class="label required">Name</label>
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
          <label for="type" class="label required">Type</label>
          <Select
            :options="ARTIFACT_TYPE_OPTIONS"
            option-label="label"
            option-value="value"
            option-disabled="disabled"
            placeholder="Select artifacts type"
            name="type"
            label-id="type"
            fluid
          ></Select>
        </div>
        <div class="field">
          <label for="stages" class="label">Stages</label>
          <UiTagsSelect
            v-model="initialValues.stages"
            id="stages"
            name="stages"
            placeholder="Type to add stages"
            :items="['Production', 'Pre-Production', 'Staging']"
          />
        </div>
      </div>
      <Button
        type="submit"
        label="Create"
        fluid
        rounded
        :loading="loading"
        :disabled="!$form.valid || loading"
      />
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import type { TrackCreateIn } from '@/lib/api/orbit-tracks/interfaces'
import { Button, Dialog, InputText, Select, Textarea, useToast } from 'primevue'
import { ARTIFACT_TYPE_OPTIONS, TRACKS_CREATOR_DIALOG_PT } from './tracks.const'
import { useTracksStore } from '@/stores/tracks'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { ref } from 'vue'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { getErrorMessage } from '@/helpers/helpers'
import z from 'zod'
import UiTagsSelect from '../ui/UiTagsSelect.vue'

const tracksStore = useTracksStore()

const toast = useToast()

const initialValues = ref({
  name: '',
  description: '',
  type: '',
  stages: ['Production', 'Pre-Production', 'Staging'],
})

const loading = ref(false)

const resolver = zodResolver(
  z.object({
    name: z.string().min(1).max(100),
    description: z.string().max(255).optional(),
    type: z.nativeEnum(ArtifactTypeEnum),
    stages: z.array(z.string().min(1).max(100)).min(1),
  }),
)

function onVisibleChange(value: boolean) {
  if (value) {
    tracksStore.showCreator()
  } else {
    tracksStore.hideCreator()
  }
}

async function onSubmit({ values, valid, reset }: FormSubmitEvent) {
  if (!valid) return

  loading.value = true
  try {
    const { name, description, type: artifact_type, stages } = values
    const payload: TrackCreateIn = {
      name,
      artifact_type,
      description,
      stages,
    }
    await tracksStore.createTrack(payload)
    tracksStore.hideCreator()
    toast.add(simpleSuccessToast('Track has been successfully created'))
    reset()
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error, 'Failed to create track')))
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
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
.textarea {
  height: 72px;
  resize: none;
}
</style>
