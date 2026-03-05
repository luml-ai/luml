<template>
  <Button label="Upload to LUML" severity="secondary" @click="uploadClick">
    <template #icon>
      <CloudUploadIcon :size="14" />
    </template>
  </Button>
  <Dialog v-model:visible="visible" header="upload to LUML" modal :pt="DIALOG_PT">
    <Form
      id="upload-form"
      ref="formRef"
      v-slot="$form"
      :initial-values="initialValues"
      :resolver="resolver"
      class="flex flex-col gap-3"
      @submit="handleSubmit"
    >
      <SelectButton name="type" :options="options" option-label="label" option-value="value" />
      <FormField name="organization" class="flex flex-col gap-2">
        <label for="organization">
          Organization <span class="text-(--p-badge-warn-background)">*</span>
        </label>
        <Select
          :options="organizations"
          option-label="label"
          option-value="value"
          placeholder="Select organization"
          :loading="loadingOrganizations"
          fluid
        />
      </FormField>
      <FormField name="orbit" class="flex flex-col gap-2">
        <label for="orbit"> Orbit <span class="text-(--p-badge-warn-background)">*</span> </label>
        <Select
          :options="orbits"
          option-label="label"
          option-value="value"
          :disabled="!$form['organization']?.value"
          :loading="loadingOrbits"
          :placeholder="$form['organization']?.value ? 'Select orbit' : 'Select organization first'"
          fluid
        >
          <template #empty>
            <div class="max-w-[423px] w-full">
              There are no orbits in this organization yet. Create your first orbit in
              <a target="_blank" :href="lmlUrl" class="text-primary font-medium hover:underline">
                LUML.
              </a>
            </div>
          </template>
        </Select>
      </FormField>
      <FormField name="collection" class="flex flex-col gap-2">
        <label for="collection">
          Collection <span class="text-(--p-badge-warn-background)">*</span>
        </label>
        <Select
          :options="collections"
          option-label="label"
          option-value="value"
          :disabled="!$form['orbit']?.value"
          :loading="loadingCollections"
          :placeholder="$form['orbit']?.value ? 'Select collection' : 'Select orbit first'"
          fluid
        >
          <template #empty>
            <div class="max-w-[423px] w-full">
              There are no collections in this orbit yet. Create your first collection in
              <a target="_blank" :href="lmlUrl" class="text-primary font-medium hover:underline">
                LUML.
              </a>
            </div>
          </template></Select
        >
      </FormField>
      <FormField name="name" class="flex flex-col gap-2">
        <label for="name"> Name <span class="text-(--p-badge-warn-background)">*</span> </label>
        <InputText id="name" placeholder="Enter name" fluid />
      </FormField>
      <FormField name="description" class="flex flex-col gap-2">
        <label for="description"> Description </label>
        <Textarea id="description" placeholder="Enter description" fluid class="h-24 resize-none" />
      </FormField>
      <FormField name="tags" class="flex flex-col gap-2">
        <label for="tags">Tags</label>
        <UiTagsSelect id="tags" :items="[]" placeholder="Type to add tags" />
      </FormField>
      <FormField
        v-if="$form['type']?.value === 'model'"
        name="embedExperiment"
        class="flex items-center gap-2"
      >
        <label for="embedExperiment">Embed experiment into model</label>
        <ToggleSwitch id="embedExperiment" />
      </FormField>
    </Form>
    <div v-if="uploading" class="mt-3">
      <ProgressBar :value="uploadPercent" />
    </div>
    <template #footer>
      <Button
        type="submit"
        form="upload-form"
        label="Export"
        fluid
        rounded
        :loading="uploading"
        :disabled="uploading"
      />
    </template>
  </Dialog>
  <ApiKeyModal v-model:visible="apiKeyModalVisible" v-model:api-key="apiKey" />
</template>

<script setup lang="ts">
import {
  Button,
  Dialog,
  SelectButton,
  Select,
  InputText,
  Textarea,
  ToggleSwitch,
  ProgressBar,
} from 'primevue'
import { CloudUploadIcon } from 'lucide-vue-next'
import { reactive, watch, ref } from 'vue'
import { FormField, Form, type FormInstance, type FormSubmitEvent } from '@primevue/forms'
import UiTagsSelect from '../ui/UiTagsSelect.vue'
import { DIALOG_PT, resolver } from './data'
import ApiKeyModal from '../api-key/ApiKeyModel.vue'
import { apiService } from '@/api/api.service'
import { useToast } from 'primevue'
import { successToast, errorToast } from '@/toasts'
import type { Model } from '@/store/experiments/experiments.interface'

const props = defineProps<{
  experimentId: string
  models: Model[]
}>()

const toast = useToast()

const options = [
  { label: 'Auto', value: 'auto' },
  { label: 'Model', value: 'model' },
  { label: 'Experiment', value: 'experiment' },
]

const initialValues = reactive({
  type: 'auto',
  organization: null,
  orbit: null,
  collection: null,
  name: '',
  description: '',
  tags: [],
  embedExperiment: false,
})

const formRef = ref<FormInstance>()
const visible = defineModel<boolean>('visible')
const apiKeyModalVisible = ref<boolean>(false)
const apiKey = ref<string | null>(null)

const organizations = ref<{ label: string; value: string }[]>([])
const orbits = ref<{ label: string; value: string }[]>([])
const collections = ref<{ label: string; value: string }[]>([])
const loadingOrganizations = ref(false)
const loadingOrbits = ref(false)
const loadingCollections = ref(false)

const uploading = ref(false)
const uploadPercent = ref(0)

const lmlUrl = import.meta.env.VITE_LUML_URL

async function loadOrganizations() {
  loadingOrganizations.value = true
  try {
    const data = await apiService.getLumlOrganizations()
    organizations.value = data.map((o: any) => ({ label: o.name, value: o.id }))
  } catch (e) {
    toast.add(errorToast(e))
  } finally {
    loadingOrganizations.value = false
  }
}

async function loadOrbits(organizationId: string) {
  loadingOrbits.value = true
  try {
    const data = await apiService.getLumlOrbits(organizationId)
    orbits.value = data.map((o: any) => ({ label: o.name, value: o.id }))
  } catch (e) {
    toast.add(errorToast(e))
  } finally {
    loadingOrbits.value = false
  }
}

async function loadCollections(organizationId: string, orbitId: string) {
  loadingCollections.value = true
  try {
    const data = await apiService.getLumlCollections(organizationId, orbitId)
    collections.value = data.items.map((c: any) => ({ label: c.name, value: c.id }))
  } catch (e) {
    toast.add(errorToast(e))
  } finally {
    loadingCollections.value = false
  }
}

function openModal() {
  visible.value = true
  loadOrganizations()
}

function openApiKeyModal() {
  apiKeyModalVisible.value = true
}

function uploadClick() {
  if (apiKey.value) openModal()
  else openApiKeyModal()
}

watch(
  () => formRef.value?.states['organization']?.value,
  (orgId) => {
    formRef.value?.setFieldValue('orbit', null)
    orbits.value = []
    collections.value = []
    if (orgId) loadOrbits(orgId)
  },
)

watch(
  () => formRef.value?.states['orbit']?.value,
  (orbitId) => {
    formRef.value?.setFieldValue('collection', null)
    collections.value = []
    const orgId = formRef.value?.states['organization']?.value
    if (orgId && orbitId) loadCollections(orgId, orbitId)
  },
)

async function handleSubmit(event: FormSubmitEvent) {
  if (!event.valid) return

  const values = event.values
  uploading.value = true
  uploadPercent.value = 0

  try {
    const response = await apiService.uploadLumlArtifact({
      upload_type: values.type,
      experiment_id: props.experimentId,
      organization_id: values.organization,
      orbit_id: values.orbit,
      collection_id: values.collection,
      name: values.name || undefined,
      description: values.description || undefined,
      tags: values.tags?.length ? values.tags : undefined,
      embed_experiment: values.embedExperiment ?? false,
    })

    const eventSource = new EventSource(`/api/luml/artifact/${response.job_id}/progress`)

    eventSource.onmessage = (ev) => {
      const data = JSON.parse(ev.data)
      if (data.type === 'complete') {
        uploadPercent.value = 100
        uploading.value = false
        visible.value = false
        eventSource.close()
        toast.add(successToast('Artifact uploaded successfully'))
      } else if (data.type === 'error') {
        uploading.value = false
        eventSource.close()
        toast.add(errorToast(data.message))
      } else if (data.type === 'progress') {
        uploadPercent.value = data.percent
      }
    }

    eventSource.onerror = () => {
      uploading.value = false
      eventSource.close()
      toast.add(errorToast('Upload connection lost'))
    }
  } catch (e) {
    uploading.value = false
    toast.add(errorToast(e))
  }
}
</script>

<style scoped></style>
