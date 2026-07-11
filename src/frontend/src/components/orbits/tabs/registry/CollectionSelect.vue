<template>
  <div class="field">
    <label :for="controlId" class="label" :class="{ required: required }">Collection</label>
    <Select
      v-model="modelValue"
      :id="controlId"
      :name="name"
      placeholder="Select collection"
      fluid
      option-label="name"
      option-value="id"
      :options="collectionsList"
      :disabled="disabled"
      :virtualScrollerOptions="virtualScrollerOptions"
      :pt="{
        overlay: 'collections-select-overlay',
      }"
    >
      <template #option="{ option }">
        <CollectionCardSmall
          :name="option.name"
          :id="option.id"
          :createdAt="option.created_at"
          :updatedAt="option.updated_at"
          :type="option.type"
          :totalArtifacts="option.total_artifacts"
        />
      </template>
    </Select>
  </div>
</template>

<script setup lang="ts">
import { useCollectionsList } from '@/hooks/useCollectionsList'
import { Select, useToast } from 'primevue'
import { useCollectionsStore } from '@/stores/collections'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { computed, watch } from 'vue'
import { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'
import CollectionCardSmall from './CollectionCardSmall.vue'

type Props = {
  controlId?: string
  required?: boolean
  name?: string
  disabled: boolean
  organizationId: string
  orbitId: string
  initialCollectionId?: string
  types?: OrbitCollectionTypeEnum[]
}

const props = withDefaults(defineProps<Props>(), {
  controlId: 'collection',
  required: false,
  name: 'collection',
})

const collectionsStore = useCollectionsStore()
const toast = useToast()
const { setRequestInfo, getInitialPage, collectionsList, reset, onLazyLoad, addCollectionsToList } =
  useCollectionsList(20, false, props.types)

const virtualScrollerOptions = computed(() => {
  if (collectionsList.value.length < 10) return undefined
  return { lazy: true, onLazyLoad: onLazyLoad, itemSize: 38 }
})

const modelValue = defineModel<string | null>()

async function addInitialCollectionToList(collectionId: string) {
  const collection = await collectionsStore.getCollection(collectionId)
  addCollectionsToList([collection])
}

async function onRequestInfoChange() {
  try {
    reset()
    if (props.initialCollectionId) {
      addInitialCollectionToList(props.initialCollectionId)
    }
    setRequestInfo({
      organizationId: props.organizationId,
      orbitId: props.orbitId,
    })
    await getInitialPage()
  } catch (e) {
    const message = getErrorMessage(e, 'Failed to load collections')
    toast.add(simpleErrorToast(message))
  }
}

watch(() => [props.organizationId, props.orbitId], onRequestInfoChange, {
  immediate: true,
  deep: true,
})
</script>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.dropdown-title {
  padding: 12px 16px 8px;
  font-size: 14px;
  font-weight: var(--p-select-option-group-font-weight);
  color: var(--p-select-option-group-color);
}
</style>

<style>
.collections-select-overlay .p-select-option {
  padding: 0;
  background-color: transparent !important;
}
.collections-select-overlay .p-select-header {
  padding-left: 4px;
  padding-right: 4px;
}
</style>
