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
      :options="TRACKS_TYPE_OPTIONS"
      option-label="label"
      option-value="value"
      size="small"
      placeholder="Filter by type"
      :pt="TRACKS_TYPE_SELECT_PT"
    />
  </div>
</template>

<script setup lang="ts">
import type { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { IconField, InputText, InputIcon, MultiSelect } from 'primevue'
import { Search } from 'lucide-vue-next'
import { TRACKS_TYPE_OPTIONS, TRACKS_TYPE_SELECT_PT } from './tracks.const'

const search = defineModel<string>('search')
const types = defineModel<ArtifactTypeEnum[]>('types', { default: [] })

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
