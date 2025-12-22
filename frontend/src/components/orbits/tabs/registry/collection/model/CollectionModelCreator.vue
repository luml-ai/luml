<template>
  <Dialog
    v-model:visible="visible"
    header="add a new model"
    modal
    :draggable="false"
    :pt="dialogPt"
  >
    <Form :initial-values="formData" :resolver="modelCreatorResolver" @submit="onSubmit">
      <div class="inputs">
        <div class="field">
          <label for="name" class="label required">Name</label>
          <InputText
            v-model="formData.name"
            id="name"
            name="name"
            placeholder="Name your model"
            fluid
          />
        </div>
        <div class="field">
          <label for="description" class="label">Description</label>
          <Textarea
            v-model="formData.description"
            name="description"
            id="description"
            placeholder="Describe your model"
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
        id="model-file"
        :file="fileInfo"
        :error="fileError"
        accept-text="Accepts .luml, .dfs, .fnnx, .pyfnx file type"
        upload-text="upload model file"
        class="file-field"
        @select-file="onSelectFile"
        @remove-file="onRemoveFile"
      />
      <div v-if="progress !== null" class="upload-section">
        <p class="upload-description">Model uploading</p>
        <ProgressBar :value="progress" showValue />
      </div>
      <Button type="submit" fluid rounded :loading="loading">Add</Button>
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import type { AutoCompleteCompleteEvent, DialogPassThroughOptions } from 'primevue'
import { useRouter } from 'vue-router'
import type { FormSubmitEvent } from '@primevue/forms'
import { computed, ref, watch } from 'vue'
import { modelCreatorResolver } from '@/utils/forms/resolvers'
import FileInput from '@/components/ui/FileInput.vue'
import { Form } from '@primevue/forms'
import { Dialog, Button, InputText, Textarea, AutoComplete, useToast, ProgressBar } from 'primevue'
import { useModelUpload } from '@/hooks/useModelUpload'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { useModelsTags } from '@/hooks/useModelsTags'

interface FormData {
  name: string
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

const { upload, progress } = useModelUpload()
const toast = useToast()
const { getTagsByQuery } = useModelsTags()
const router = useRouter()

const visible = defineModel<boolean>('visible')
const loading = ref(false)
const formData = ref<FormData>({
  name: '',
  description: '',
  file: null,
  tags: [],
})
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

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = getTagsByQuery(event.query)
}

function checkFileSize(size: number) {
  return size < 524288000
}

function onSelectFile(event: File) {
  fileError.value = false
  const regex = /^[^:\"*\`~#%;'^]+\.[^\s:\"*\`~#%;'^]+$/
  const isFileNameCorrect = regex.test(event.name)
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
  const isDfs = fileName.endsWith('.dfs')
  const isFnnx = fileName.endsWith('.fnnx')
  const isPyfnx = fileName.endsWith('.pyfnx')
  const isLuml = fileName.endsWith('.luml')
  return isDfs || isFnnx || isPyfnx || isLuml
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
      formData.value.description,
      formData.value.tags,
    )
    toast.add({
      severity: 'success',
      summary: 'Success',
      detail: `${formData.value.name}has been added to the collection successfully.<br><a href="#" class="toast-action-link" data-route="orbit-registry" data-params="{}">Go to Collection</a>`,
      life: 5000,
    })
    formData.value.description = ''
    formData.value.file = null
    formData.value.name = ''
    formData.value.tags = []
    visible.value = false
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e?.message || 'Failed file upload'))
  } finally {
    loading.value = false
  }
}

watch(visible, (val) => {
  if (!val) {
    formData.value = {
      name: '',
      description: '',
      file: null,
      tags: [],
    }
    fileError.value = false
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
