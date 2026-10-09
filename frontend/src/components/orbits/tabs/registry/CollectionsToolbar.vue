<template>
  <div class="toolbar">
    <div class="rich-control search-control">
      <IconField>
        <InputText
          :model-value="search"
          size="small"
          placeholder="Search"
          class="rich-control-item"
          @update:model-value="updateSearch"
        />
        <InputIcon>
          <Search :size="12" />
        </InputIcon>
      </IconField>
      <Button
        severity="secondary"
        variant="outlined"
        size="small"
        class="rich-control-button"
        @click="clearSearch"
      >
        <template #icon>
          <X :size="12" />
        </template>
      </Button>
    </div>
    <div class="rich-control type-control">
      <MultiSelect
        v-model="types"
        :options="COLLECTION_TYPE_OPTIONS"
        option-label="label"
        option-value="value"
        size="small"
        placeholder="Type"
        :pt="COLLECTION_TYPE_SELECT_PT"
        class="rich-control-item"
      />
      <Button
        severity="secondary"
        variant="outlined"
        size="small"
        class="rich-control-button"
        @click="clearTypes"
      >
        <template #icon>
          <X :size="12" />
        </template>
      </Button>
    </div>
    <div class="rich-control tag-control">
      <UiRichTagsSelect v-model="tags" :options="collectionsStore.collectionsTags" />
      <Button
        severity="secondary"
        variant="outlined"
        size="small"
        class="rich-control-button"
        @click="clearTags"
      >
        <template #icon>
          <X :size="12" />
        </template>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'
import { IconField, InputText, InputIcon, MultiSelect, Button } from 'primevue'
import { Search, X } from 'lucide-vue-next'
import { COLLECTION_TYPE_OPTIONS, COLLECTION_TYPE_SELECT_PT } from './collection.const'
import { useCollectionsStore } from '@/stores/collections'
import UiRichTagsSelect from '@/components/ui/UiRichTagsSelect.vue'

const collectionsStore = useCollectionsStore()

const search = defineModel<string>('search')
const types = defineModel<OrbitCollectionTypeEnum[]>('types', { default: [] })
const tags = defineModel<string[]>('tags', { default: [] })

function updateSearch(val: string | undefined) {
  search.value = val
}

function clearSearch() {
  if (!search.value) return
  search.value = undefined
}

function clearTypes() {
  if (types.value.length === 0) return
  types.value = []
}

function clearTags() {
  if (tags.value.length === 0) return
  tags.value = []
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 20px;
}

.search-control {
  max-width: 240px;
}

.type-control {
  max-width: 183px;
}

.rich-control {
  display: flex;
}

.rich-control-item {
  border-radius: 8px 0 0 8px;
  height: 100%;
}

.rich-control-button {
  border-radius: 0 8px 8px 0;
  border-left: none !important;
  background-color: var(--p-inputtext-background);
  border-color: var(--p-inputtext-border-color) !important;
  width: 23px !important;
  padding: 0;
  flex-shrink: 0;
}

:deep(.p-iconfield) {
  max-width: 237px;
}

:deep(.p-iconfield .p-inputicon:last-child) {
  inset-inline-end: 9px;
}

:deep(.p-iconfield .p-inputtext) {
  width: 100%;
}
</style>
