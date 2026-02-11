<template>
  <div class="toolbar">
    <IconField>
      <InputText
        :model-value="search"
        size="small"
        placeholder="Search"
        @update:model-value="updateSearch"
      />
      <InputIcon>
        <Search :size="12" />
      </InputIcon>
    </IconField>
    <MultiSelect
      v-model="types"
      :options="COLLECTION_TYPE_OPTIONS"
      option-label="label"
      option-value="value"
      size="small"
      placeholder="Filter by type"
      :pt="COLLECTION_TYPE_SELECT_PT"
    />
  </div>
</template>

<script setup lang="ts">
import type { OrbitCollectionTypeEnum } from '@/lib/api/orbit-collections/interfaces'
import { IconField, InputText, InputIcon, MultiSelect } from 'primevue'
import { Search } from 'lucide-vue-next'
import { COLLECTION_TYPE_OPTIONS, COLLECTION_TYPE_SELECT_PT } from './collection.const'

const search = defineModel<string>('search')
const types = defineModel<OrbitCollectionTypeEnum[]>('types', { default: [] })

function updateSearch(val: string | undefined) {
  search.value = val
}
</script>

<style scoped>
.toolbar {
  margin-bottom: 16px;
  display: flex;
  align-items: center;
  gap: 12px;
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
