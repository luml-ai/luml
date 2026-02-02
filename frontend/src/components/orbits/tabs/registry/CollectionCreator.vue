<template>
  <Dialog
    v-model:visible="visible"
    header="Create a new collection"
    modal
    :draggable="false"
    :pt="COLLECTION_CREATOR_DIALOG_PT"
  >
    <Form :initial-values="formData" :resolver="collectionCreatorResolver" @submit="onSubmit">
      <div class="inputs">
        <div class="field">
          <label for="name" class="label required">Name</label>
          <InputText
            v-model="formData.name"
            id="name"
            name="name"
            placeholder="Name your collection"
            fluid
          />
        </div>
        <div class="field">
          <label for="collection_type" class="label required">Type</label>
          <Select
            v-model="formData.collection_type"
            :options="COLLECTION_TYPE_OPTIONS"
            option-label="label"
            option-value="value"
            option-disabled="disabled"
            placeholder="Select artifact types"
            name="collection_type"
            id="collection_type"
          ></Select>
        </div>
        <div class="field">
          <label for="description" class="label">Description</label>
          <Textarea
            v-model="formData.description"
            name="description"
            id="description"
            placeholder="Describe your collection"
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

      <Button type="submit" fluid rounded :loading="loading">Create</Button>
    </Form>
  </Dialog>
</template>

<script setup lang="ts">
import type { AutoCompleteCompleteEvent } from 'primevue'
import { Dialog, Button, InputText, Select, AutoComplete, Textarea, useToast } from 'primevue'
import { Form, type FormSubmitEvent } from '@primevue/forms'
import { computed, ref } from 'vue'
import {
  OrbitCollectionTypeEnum,
  type OrbitCollectionCreator,
} from '@/lib/api/orbit-collections/interfaces'
import { useCollectionsStore } from '@/stores/collections'
import { simpleErrorToast, simpleSuccessToast } from '@/lib/primevue/data/toasts'
import { collectionCreatorResolver } from '@/utils/forms/resolvers'
import { COLLECTION_CREATOR_DIALOG_PT, COLLECTION_TYPE_OPTIONS } from './collection.const'

type Props = {
  organizationId?: string
  orbitId?: string
}

const props = defineProps<Props>()

const collectionsStore = useCollectionsStore()
const toast = useToast()

const visible = defineModel<boolean>('visible')

const formData = ref<OrbitCollectionCreator>({
  description: '',
  name: '',
  collection_type: OrbitCollectionTypeEnum.model,
  tags: [],
})
const loading = ref(false)

const existingTags = computed(() => {
  const tagsSet = collectionsStore.collectionsList.reduce((acc: Set<string>, item) => {
    item.tags.map((tag) => {
      acc.add(tag)
    })
    return acc
  }, new Set<string>())
  return Array.from(tagsSet)
})
const autocompleteItems = ref<string[]>([])

function searchTags(event: AutoCompleteCompleteEvent) {
  autocompleteItems.value = [
    event.query,
    ...existingTags.value.filter((tag) => tag.toLowerCase().includes(event.query.toLowerCase())),
  ]
}

function getRequestInfo() {
  if (props.organizationId && props.orbitId) {
    return { organizationId: props.organizationId, orbitId: props.orbitId }
  }
}

async function onSubmit({ valid }: FormSubmitEvent) {
  if (!valid) return
  try {
    loading.value = true
    await collectionsStore.createCollection({ ...formData.value }, getRequestInfo())
    visible.value = false
    toast.add(simpleSuccessToast('Collection created'))
  } catch (e: any) {
    toast.add(
      simpleErrorToast(e?.response?.data?.detail || e.message || 'Failed to create collection'),
    )
  } finally {
    loading.value = false
  }
}
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
