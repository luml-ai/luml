<template>
  <Dialog
    v-model:visible="visible"
    header="add a new artifact"
    modal
    :draggable="false"
    :pt="dialogPt"
  >
    <Form :initial-values="formData" :resolver="artifactCreateResolver" @submit="onSubmit">
      <div class="inputs">
        <div class="field">
          <label for="name" class="label required">Name</label>
          <InputText
            v-model="formData.name"
            id="name"
            name="name"
            placeholder="Name your artifact"
            fluid
          />
        </div>
        <div class="field">
          <label for="collection_type" class="label required">Type</label>
          <Select
            v-model="formData.type"
            :options="ARTIFACT_TYPE_OPTIONS"
            option-label="label"
            option-value="value"
            option-disabled="disabled"
            placeholder="Select artifact types"
            name="type"
            id="type"
          ></Select>
        </div>
        <div class="field">
          <label for="description" class="label">Description</label>
          <Textarea
            v-model="formData.description"
            name="description"
            id="description"
            placeholder="Describe your artifact"
            style="height: 72px; resize: none"
          ></Textarea>
        </div>
        <div class="field">
          <label for="tags" class="label">Tags</label>
          <AutoComplete
            v-model="formData.tags"
            id="tags"
            name="tags"
            placeholder="Type to add tags"
            fluid
            multiple
            :suggestions="autocompleteItems"
            @complete="searchTags"
          ></AutoComplete>
        </div>
      </div>
      <FileInput
        id="artifact-file"
        :file="fileInfo"
        :error="fileError"
        :accept-text="fileInputAcceptText"
        upload-text="upload artifact file"
        class="file-field"
        @select-file="onSelectFile"
        @remove-file="onRemoveFile"
      />
      <div v-if="progress !== null" class="upload-section">
        <p class="upload-description">Artifact uploading</p>
        <ProgressBar :value="progress" showValue />
      </div>
      <Button type="submit" fluid rounded :loading="loading">Add</Button>
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import type { AutoCompleteCompleteEvent, DialogPassThroughOptions } from 'primevue'
import type { FormSubmitEvent } from '@primevue/forms'
import { useRoute } from 'vue-router'
import { computed, ref, watch } from 'vue'
import { artifactCreateResolver } from '@/utils/forms/resolvers'
import { Form } from '@primevue/forms'
import {
  Dialog,
  Button,
  InputText,
  Textarea,
  AutoComplete,
  useToast,
  ProgressBar,
  Select,
} from 'primevue'
import { useArtifactUpload } from '@/hooks/useArtifactUpload'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { useArtifactsTags } from '@/hooks/useArtifactsTags'
import { getErrorMessage } from '@/helpers/helpers'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { isCorrectFileName, isDatasetFile, isExperimentFile, isModelFile } from '@/helpers/files'
import FileInput from '@/components/ui/FileInput.vue'

interface FormData {
  name: string
  type: ArtifactTypeEnum
  description: string
  file: File | null
  tags: string[]
}

const dialogPt: DialogPassThroughOptions = {
  root: {
    style: 'max-width: 500px; width: 100%;',
  },
  header: {
    style: 'padding: 28px; text-transform: uppercase; font-size: 20px;',
  },
  content: {
    style: 'padding: 0 28px 28px;',
  },
}

const initialFormData = {
  name: '',
  type: ArtifactTypeEnum.model,
  description: '',
  file: null,
  tags: [],
}

const ARTIFACT_TYPE_OPTIONS = [
  { label: 'Model', value: ArtifactTypeEnum.model, disabled: false },
  { label: 'Dataset', value: ArtifactTypeEnum.dataset, disabled: true },
  { label: 'Experiment', value: ArtifactTypeEnum.experiment, disabled: true },
]

const { upload, progress } = useArtifactUpload()
const { getTagsByQuery, loadTags } = useArtifactsTags()
const toast = useToast()
const route = useRoute()

const visible = defineModel<boolean>('visible')
const loading = ref(false)
const formData = ref<FormData>(initialFormData)
const fileError = ref(false)
const autocompleteItems = ref<string[]>([])

const fileInfo = computed(() => {
  const file = formData.value.file
  if (!file) return {}
  return {
    name: file.name,
    size: file.size,
  }
})

const fileInputAcceptText = computed(() => {
  if (formData.value.type === ArtifactTypeEnum.model) {
    return 'Accepts .luml, .dfs, .fnnx, .pyfnx file type'
  } else if (formData.value.type === ArtifactTypeEnum.experiment) {
    return 'Accepts experiment file type'
  } else if (formData.value.type === ArtifactTypeEnum.dataset) {
    return 'Accepts dataset file type'
  } else return ''
})

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = getTagsByQuery(event.query)
}

function checkFileSize(size: number) {
  return size < 524288000
}

function onSelectFile(event: File) {
  fileError.value = false
  const isFileNameCorrect = isCorrectFileName(event.name)
  const isCorrectFileFormat = checkFileFormat(event.name)
  const fileSizeCorrect = checkFileSize(event.size)
  if (isCorrectFileFormat && isFileNameCorrect && fileSizeCorrect) {
    formData.value.file = event
  } else {
    fileError.value = true
    !isFileNameCorrect && toast.add(simpleErrorToast('Incorrect file name'))
  }
}

function checkFileFormat(fileName: string) {
  if (formData.value.type === ArtifactTypeEnum.model) {
    return isModelFile(fileName)
  } else if (formData.value.type === ArtifactTypeEnum.experiment) {
    return isExperimentFile(fileName)
  } else if (formData.value.type === ArtifactTypeEnum.dataset) {
    return isDatasetFile(fileName)
  }
  return false
}

function onRemoveFile() {
  fileError.value = false
  formData.value.file = null
}

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid || !formData.value.file) return

  loading.value = true

  try {
    await upload(
      formData.value.file,
      formData.value.name,
      formData.value.type,
      formData.value.description,
      formData.value.tags,
    )
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: `${formData.value.name} has been added to the collection successfully.<br><a href="#" class="toast-action-link" data-route="orbit-registry" data-params="{}">Go to Collection</a>`,
      life: 5000,
    })
    reset()
    visible.value = false
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e?.message || 'Failed file upload'))
  } finally {
    loading.value = false
  }
}

function reset() {
  formData.value = initialFormData
  resetFile()
}

function resetFile() {
  formData.value.file = null
  fileError.value = false
}

async function initTags() {
  try {
    loadTags(
      String(route.params.organizationId),
      String(route.params.id),
      String(route.params.collectionId),
    )
  } catch (e: unknown) {
    const message = getErrorMessage(e, 'Failed to load tags')
    toast.add(simpleErrorToast(message))
  }
}

watch(visible, (val) => {
  val ? initTags() : reset()
})

watch(() => formData.value.type, resetFile)
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

.file-field {
  margin-bottom: 28px;
}

.upload-section {
  margin-bottom: 28px;
}

.upload-description {
  margin-bottom: 8px;
}
</style>
