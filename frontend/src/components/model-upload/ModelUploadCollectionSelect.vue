<template>
  <div class="field">
    <label for="name" class="label required">Collection</label>
    <Select
      v-model="modelValue"
      id="collection"
      name="collection"
      :placeholder="orbitId ? 'Select collection' : 'Select orbit first'"
      :disabled="!orbitId"
      fluid
      filter
      :options="collectionsList"
      option-label="name"
      option-value="id"
      :virtualScrollerOptions="virtualScrollerOptions"
      @filter="onFilter"
    >
      <template #footer>
        <div class="select-footer">
          <Button
            label="Create new collection"
            variant="text"
            @click="collectionCreatorVisible = true"
          >
            <template #icon>
              <Plus :size="14" />
            </template>
          </Button>
        </div>
      </template>
    </Select>
  </div>
  <CollectionCreator
    v-if="organizationId && orbitId"
    :organization-id="organizationId"
    :orbit-id="orbitId"
    v-model:visible="collectionCreatorVisible"
  ></CollectionCreator>
</template>

<script setup lang="ts">
import { Select, Button, useToast, type SelectFilterEvent } from 'primevue'
import { useCollectionsList } from '@/hooks/useCollectionsList'
import { getErrorMessage } from '@/helpers/helpers'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { watch, ref } from 'vue'
import { useDebounceFn } from '@vueuse/core'
import { Plus } from 'lucide-vue-next'
import CollectionCreator from '../orbits/tabs/registry/CollectionCreator.vue'

type Props = {
  organizationId: string
  orbitId: string | null
}

const props = defineProps<Props>()

const modelValue = defineModel<string | null>('modelValue')

const toast = useToast()
const { setRequestInfo, getInitialPage, collectionsList, reset, onLazyLoad, setSearchQuery } =
  useCollectionsList()

const virtualScrollerOptions = {
  lazy: true,
  onLazyLoad: onLazyLoad,
  itemSize: 38,
}

const collectionCreatorVisible = ref(false)

async function onRequestInfoChange() {
  try {
    reset()
    modelValue.value = null
    if (!props.orbitId) return
    setRequestInfo({
      organizationId: String(props.organizationId),
      orbitId: props.orbitId,
    })
    await getInitialPage()
  } catch (e) {
    toast.add(simpleErrorToast(getErrorMessage(e, 'Failed to load collections')))
  }
}

const debouncedOnRequestInfoChange = useDebounceFn(onRequestInfoChange, 500)

function onFilter(event: SelectFilterEvent) {
  setSearchQuery(event.value)
  debouncedOnRequestInfoChange()
}

watch(() => props.orbitId, onRequestInfoChange, { immediate: true })
</script>

<style scoped>
.field {
  display: flex;
  flex-direction: column;
  gap: 7px;
}

.label {
  align-self: flex-start;
  font-size: 14px;
}

.select-footer {
  margin: 0 12px;
  padding: 4px 0;
  border-top: 1px solid var(--p-divider-border-color);
}
</style>
