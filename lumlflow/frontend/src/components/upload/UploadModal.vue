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
          option-label="label"
          option-value="value"
          placeholder="Select organization"
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
        v-if="$form['type']?.value === 'auto'"
        name="embedExperiment"
        class="flex items-center gap-2"
      >
        <label for="embedExperiment">Embed experiment into model</label>
        <ToggleSwitch id="embedExperiment" />
      </FormField>
    </Form>
    <template #footer>
      <Button type="submit" form="upload-form" label="Export" fluid rounded />
    </template>
  </Dialog>
  <ApiKeyModal v-model:visible="apiKeyModalVisible" />
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
  useToast,
} from 'primevue'
import { CloudUploadIcon } from 'lucide-vue-next'
import { reactive, watch } from 'vue'
import { ref } from 'vue'
import { FormField, Form, type FormInstance } from '@primevue/forms'
import { DIALOG_PT, resolver, selectTypeOptions } from './data'
import { useAuthStore } from '@/store/auth'
import { errorToast } from '@/toasts'
import UiTagsSelect from '../ui/UiTagsSelect.vue'
import ApiKeyModal from '../api-key/ApiKeyModal.vue'

const authStore = useAuthStore()
const toast = useToast()

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
const apiKeyModalVisible = ref<boolean>(false)
const loading = ref<boolean>(false)

const organizations = ref<unknown[]>([
  {
    label: 'Organization 1',
    value: 'organization-1',
  },
  {
    label: 'Organization 2',
    value: 'organization-2',
  },
])
const orbits = ref<unknown[]>([
  {
    label: 'Orbit 1',
    value: 'orbit-1',
  },
  {
    label: 'Orbit 2',
    value: 'orbit-2',
  },
])
const collections = ref<unknown[]>([
  {
    label: 'Collection 1',
    value: 'collection-1',
  },
  {
    label: 'Collection 2',
    value: 'collection-2',
  },
])

const lmlUrl = import.meta.env.VITE_LUML_URL

function openModal() {
  visible.value = true
}

function openApiKeyModal() {
  apiKeyModalVisible.value = true
}

async function uploadClick() {
  loading.value = true
  try {
    const isAuthenticated = await authStore.checkAuth()
    if (isAuthenticated) openModal()
    else openApiKeyModal()
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
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

watch(apiKeyModalVisible, (v) => {
  if (!v && authStore.isAuthenticated) openModal()
})
</script>

<style scoped></style>
