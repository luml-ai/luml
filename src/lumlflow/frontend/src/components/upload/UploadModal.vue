<template>
  <Button label="Upload to LUML" severity="secondary" @click="uploadClick" :loading="loading">
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
      <SelectButton
        name="type"
        :options="selectTypeOptions"
        option-label="label"
        option-value="value"
      />
      <FormField name="organization" class="flex flex-col gap-2">
        <label for="organization">
          Organization <span class="text-(--p-badge-warn-background)">*</span>
        </label>
        <Select
          :options="organizations"
          option-label="name"
          option-value="id"
          placeholder="Select organization"
          fluid
        />
      </FormField>
      <FormField name="orbit" class="flex flex-col gap-2">
        <label for="orbit"> Orbit <span class="text-(--p-badge-warn-background)">*</span> </label>
        <Select
          :options="orbits"
          option-label="name"
          option-value="id"
          :disabled="!$form['organization']?.value"
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
      <CollectionField
        fieldName="collection"
        :organization-id="$form['organization']?.value"
        :orbit-id="$form['orbit']?.value"
        :form-ref="formRef"
        @change-collection="handleChangeCollection"
      />
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
        <UiTagsSelect id="tags" :items="existingTags" placeholder="Type to add tags" />
      </FormField>
      <FormField
        v-show="$form['type']?.value === UploadTypeEnum.MODEL"
        name="embedExperiment"
        class="flex items-center gap-2"
      >
        <label for="embedExperiment">Embed experiment into model</label>
        <ToggleSwitch id="embedExperiment" />
      </FormField>
    </Form>
    <template #footer>
      <div class="flex flex-col gap-4 w-full">
        <Button
          type="submit"
          form="upload-form"
          label="Export"
          fluid
          rounded
          :loading="uploadLoading"
        />
        <ProgressBar
          v-if="progress !== null && progress !== undefined"
          :value="progress"
          class="rounded-full!"
        ></ProgressBar>
      </div>
    </template>
  </Dialog>
</template>

<script setup lang="ts">
import {
  UploadTypeEnum,
  type CollectionInfo,
  type OrbitInfo,
  type OrganizationInfo,
  type UploadArtifactPayload,
  type UploadModalProps,
} from './upload.interface'
import {
  Button,
  Dialog,
  SelectButton,
  Select,
  InputText,
  Textarea,
  ToggleSwitch,
  useToast,
  ProgressBar,
} from 'primevue'
import { CloudUploadIcon } from 'lucide-vue-next'
import { reactive, watch } from 'vue'
import { ref } from 'vue'
import { FormField, Form, type FormInstance, type FormSubmitEvent } from '@primevue/forms'
import { DIALOG_PT, resolver, selectTypeOptions } from './data'
import { useAuthStore } from '@/store/auth'
import { errorToast, successToast } from '@/toasts'
import { apiService } from '@/api/api.service'
import { useUpload } from '@/hooks/useUpload'
import UiTagsSelect from '../ui/UiTagsSelect.vue'
import CollectionField from './CollectionField.vue'

const props = defineProps<UploadModalProps>()

const authStore = useAuthStore()
const toast = useToast()
const { progress, loading: uploadLoading, error, complete, upload } = useUpload()

const initialValues = reactive({
  type: 'auto',
  organization: null,
  orbit: null,
  collection: null,
  name: '',
  description: '',
  tags: [],
  embedExperiment: true,
})

const formRef = ref<FormInstance>()

const visible = defineModel<boolean>('visible')
const loading = ref<boolean>(false)

const organizations = ref<OrganizationInfo[]>([])
const organizationsLoading = ref<boolean>(false)

const orbits = ref<OrbitInfo[]>([])
const orbitsLoading = ref<boolean>(false)

const existingTags = ref<string[]>([])

const lmlUrl = import.meta.env.VITE_LUML_URL

function openModal() {
  visible.value = true
}

async function uploadClick() {
  loading.value = true
  try {
    const isAuthenticated = await authStore.checkAuth()
    if (isAuthenticated) openModal()
    else authStore.showApiKeyModal()
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}

async function getOrganizations() {
  try {
    organizationsLoading.value = true
    organizations.value = await apiService.getLumlOrganizations()
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    organizationsLoading.value = false
  }
}

async function getOrbits(organizationId: string) {
  try {
    orbitsLoading.value = true
    orbits.value = await apiService.getLumlOrbits(organizationId)
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    orbitsLoading.value = false
  }
}

function handleChangeCollection(collection: CollectionInfo | undefined) {
  existingTags.value = collection?.tags || []
}

function handleSubmit(event: FormSubmitEvent) {
  if (!event.valid) return
  const payload: UploadArtifactPayload = {
    upload_type: event.values.type,
    embed_experiment: event.values.embedExperiment,
    experiment_id: props.experimentId,
    organization_id: event.values.organization,
    orbit_id: event.values.orbit,
    collection_id: event.values.collection,
    artifact: {
      name: event.values.name,
      description: event.values.description,
      tags: event.values.tags,
    },
  }
  upload(payload)
}

watch(
  () => formRef.value?.states['organization']?.value,
  () => {
    formRef.value?.setFieldValue('orbit', null)
  },
)

watch(
  () => formRef.value?.states['orbit']?.value,
  () => {
    formRef.value?.setFieldValue('collection', null)
  },
)

watch(visible, async (value) => {
  if (value) {
    await getOrganizations()
  } else {
    organizations.value = []
    formRef.value?.setFieldValue('organization', null)
  }
})

watch(
  () => formRef.value?.states['organization']?.value,
  async (value) => {
    if (value) {
      await getOrbits(value)
    } else {
      orbits.value = []
      formRef.value?.setFieldValue('orbit', null)
    }
  },
)

watch(error, (value) => {
  if (value) {
    toast.add(errorToast(new Error(value)))
  }
})

watch(complete, (value) => {
  if (value) {
    toast.add(successToast('Successfully uploaded to LUML'))
  }
})
</script>

<style scoped></style>
