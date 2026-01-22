<template>
  <div class="field">
    <label for="collectionId" class="label required">Collection</label>
    <Select
      v-model="modelValue"
      id="collectionId"
      name="collectionId"
      placeholder="Select collection"
      fluid
      option-label="name"
      option-value="id"
      :options="collectionsList"
      :disabled="disabled"
      :virtualScrollerOptions="virtualScrollerOptions"
    >
      <template #header>
        <div class="dropdown-title">Available collection</div>
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
import { watch } from 'vue'

type Props = {
  disabled: boolean
  organizationId: string
  orbitId: string
  initialCollectionId?: string
}

const props = defineProps<Props>()

const collectionsStore = useCollectionsStore()
const toast = useToast()
const { setRequestInfo, getInitialPage, collectionsList, reset, onLazyLoad, addCollectionsToList } =
  useCollectionsList(20, false)

const virtualScrollerOptions = {
  lazy: true,
  onLazyLoad: onLazyLoad,
  itemSize: 38,
}

const modelValue = defineModel<string | null>('modelValue')

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
