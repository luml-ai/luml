<template>
  <Dialog
    v-model:visible="visible"
    header="upload model to registry"
    modal
    :draggable="false"
    :pt="dialogPt"
  >
    <Form :initial-values="formData" :resolver="modelUploadResolver" @submit="onSubmit">
      <div class="inputs">
        <div class="field">
          <label for="name" class="label required">Orbit</label>
          <Select
            v-model="formData.orbit"
            id="orbit"
            name="orbit"
            placeholder="Select orbit"
            fluid
            :options="orbitsStore.orbitsList"
            option-label="name"
            option-value="id"
          />
        </div>
        <ModelUploadCollectionSelect
          v-model="formData.collection"
          :organization-id="organizationId"
          :orbit-id="formData.orbit"
        />
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
      <Button type="submit" fluid rounded :loading="loading">Upload</Button>
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import type { AutoCompleteCompleteEvent, DialogPassThroughOptions } from 'primevue'
import type { Tasks } from '@/lib/data-processing/interfaces'
import { computed, onBeforeMount, ref, watch } from 'vue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { Button, Select, Dialog, InputText, Textarea, AutoComplete, useToast } from 'primevue'
import { useOrbitsStore } from '@/stores/orbits'
import { useOrganizationStore } from '@/stores/organization'
import { useModelsTags } from '@/hooks/useModelsTags'
import { useModelUpload } from '@/hooks/useModelUpload'
import { modelUploadResolver } from '@/utils/forms/resolvers'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import ModelUploadCollectionSelect from './ModelUploadCollectionSelect.vue'

type Props = {
  modelBlob: Blob
  currentTask?: Tasks | 'prompt_optimization'
  fileName?: string
}

const props = defineProps<Props>()

interface FormData {
  orbit: string | null
  collection: string | null
  name: string
  description: string
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

const visible = defineModel<boolean>('visible')
const organizationStore = useOrganizationStore()
const orbitsStore = useOrbitsStore()
const toast = useToast()
const { getTagsByQuery, loadTags } = useModelsTags()
const { upload } = useModelUpload()

const loading = ref(false)
const formData = ref<FormData>({
  orbit: null,
  collection: null,
  name: '',
  description: '',
  tags: [],
})
const autocompleteItems = ref<string[]>([])

const organizationId = computed(() => {
  if (!organizationStore.currentOrganization?.id) throw new Error('Current organization not found')
  return organizationStore.currentOrganization.id
})

async function getOrbitsList() {
  await orbitsStore.loadOrbitsList(organizationId.value)
}

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = getTagsByQuery(event.query)
}

async function onCollectionChange(collectionId: string | null) {
  if (collectionId) {
    if (!formData.value.orbit) throw new Error('Orbit was not found')
    await loadTags(organizationId.value, formData.value.orbit, collectionId)
  }
}

function getRequestInfo() {
  if (!formData.value.orbit) throw new Error('Orbit was not found')
  if (!formData.value.collection) throw new Error('Collection not found')

  return {
    organizationId: organizationId.value,
    orbitId: formData.value.orbit,
    collectionId: formData.value.collection,
  }
}

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return

  try {
    loading.value = true
    const timestamp = Date.now()
    const filename = props.fileName ? props.fileName : `${props.currentTask}_${timestamp}.luml`
    const file = new File([props.modelBlob], filename)
    const ids = getRequestInfo()
    await upload(
      file,
      formData.value.name,
      formData.value.description,
      [...formData.value.tags],
      ids,
    )
    toast.add(
      simpleSuccessToast(`${formData.value.name} has been added to the collection successfully.`),
    )
    visible.value = false
  } catch (e: any) {
    toast.add(simpleErrorToast(e?.response?.data?.detail || e?.message || 'Failed file upload'))
  } finally {
    loading.value = false
  }
}

onBeforeMount(async () => {
  await getOrbitsList()
})

watch(() => formData.value.collection, onCollectionChange)
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
