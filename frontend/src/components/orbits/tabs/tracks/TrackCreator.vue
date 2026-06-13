<template>
  <Dialog
    v-model:visible="visible"
    header="Create a new track"
    modal
    :draggable="false"
    :pt="TRACK_CREATOR_DIALOG_PT"
  >
    <Form :initial-values="formData" :resolver="trackCreatorResolver" @submit="onSubmit">
      <div class="inputs">
        <div class="field">
          <label for="name" class="label required">Name</label>
          <InputText
            v-model="formData.name"
            id="name"
            name="name"
            placeholder="Name your track"
            fluid
          />
        </div>
        <div class="field">
          <label for="description" class="label">Description</label>
          <Textarea
            v-model="formData.description"
            name="description"
            id="description"
            placeholder="Describe your track"
            style="height: 72px; resize: none"
          ></Textarea>
        </div>
        <div class="field">
          <label for="artifact_type" class="label required">Type</label>
          <Select
            v-model="formData.artifact_type"
            :options="TRACK_TYPE_OPTIONS"
            option-label="label"
            option-value="value"
            option-disabled="disabled"
            placeholder="Select artifact type"
            name="artifact_type"
            id="artifact_type"
          ></Select>
        </div>
      </div>

      <Button type="submit" fluid rounded :loading="loading">Create track</Button>
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import { Dialog, Button, InputText, Select, Textarea, useToast } from 'primevue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { ref, watch } from 'vue'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { TrackCreateIn } from '@/lib/api/orbit-tracks/interfaces'
import { useTracksStore } from '@/stores/tracks'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { trackCreatorResolver } from '@/utils/forms/resolvers'
import { TRACK_CREATOR_DIALOG_PT, TRACK_TYPE_OPTIONS } from './track.const'

type Props = {
  organizationId?: string
  orbitId?: string
}

const props = defineProps<Props>()

const tracksStore = useTracksStore()
const toast = useToast()

const visible = defineModel<boolean>('visible')

const formData = ref<TrackCreateIn>({
  name: '',
  description: '',
  artifact_type: ArtifactTypeEnum.model,
})
const loading = ref(false)

function getRequestInfo() {
  if (props.organizationId && props.orbitId) {
    return { organizationId: props.organizationId, orbitId: props.orbitId }
  }
}

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return
  try {
    loading.value = true
    await tracksStore.createTrack({ ...formData.value }, getRequestInfo())
    visible.value = false
    toast.add(simpleSuccessToast('Track created'))
  } catch (e: any) {
    toast.add(
      simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create track'),
    )
  } finally {
    loading.value = false
  }
}

watch(visible, (value) => {
  if (value) {
    formData.value = {
      name: '',
      description: '',
      artifact_type: ArtifactTypeEnum.model,
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
