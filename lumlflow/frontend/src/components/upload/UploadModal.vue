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
  <ApiKeyModal v-model:visible="apiKeyModalVisible" v-model:api-key="apiKey" />
</template>

<script setup lang="ts">
import { Button, Dialog, SelectButton, Select, InputText, Textarea, ToggleSwitch } from 'primevue'
import { CloudUploadIcon } from 'lucide-vue-next'
import { reactive, watch } from 'vue'
import { zodResolver } from '@primevue/forms/resolvers/zod'
import { ref } from 'vue'
import { FormField, Form, type FormInstance } from '@primevue/forms'
import z from 'zod'
import UiTagsSelect from '../ui/UiTagsSelect.vue'
import { DIALOG_PT } from './data'
import ApiKeyModal from '../api-key/ApiKeyModel.vue'

const options = [
  {
    label: 'Auto',
    value: 'auto',
  },
  {
    label: 'Model',
    value: 'model',
  },
  {
    label: 'Experiment',
    value: 'experiment',
  },
]

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

const resolver = zodResolver(
  z
    .object({
      type: z.enum(['auto', 'model', 'experiment']),
      organization: z.string().nullable(),
      orbit: z.string().nullable(),
      collection: z.string().nullable(),
      name: z.string().min(3).max(255),
      description: z
        .string()
        .max(255)
        .refine((val) => !val || val.length >= 3, {
          message: 'Description must be at least 3 characters if not empty',
        }),
      tags: z.array(z.string().min(3).max(255)),
      embedExperiment: z.boolean(),
    })
    .superRefine((data, ctx) => {
      if (!data.organization) {
        ctx.addIssue({
          path: ['organization'],
          code: z.ZodIssueCode.custom,
          message: 'Organization is required',
        })
      }

      if (data.organization && !data.orbit) {
        ctx.addIssue({
          path: ['orbit'],
          code: z.ZodIssueCode.custom,
          message: 'Orbit is required',
        })
      }

      if (data.orbit && !data.collection) {
        ctx.addIssue({
          path: ['collection'],
          code: z.ZodIssueCode.custom,
          message: 'Collection is required',
        })
      }
    }),
)

const formRef = ref<FormInstance>()

const visible = defineModel<boolean>('visible')
const apiKeyModalVisible = ref<boolean>(false)
const apiKey = ref<string | null>(null)

const organizations = ref<any[]>([
  {
    label: 'Organization 1',
    value: 'organization-1',
  },
  {
    label: 'Organization 2',
    value: 'organization-2',
  },
])
const orbits = ref<any[]>([
  {
    label: 'Orbit 1',
    value: 'orbit-1',
  },
  {
    label: 'Orbit 2',
    value: 'orbit-2',
  },
])
const collections = ref<any[]>([
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

function uploadClick() {
  if (apiKey.value) openModal()
  else openApiKeyModal()
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
</script>

<style scoped></style>
