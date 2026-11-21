<template>
  <div class="toolbar">
    <div>
      <h2 v-if="showTitle" class="title">Dynamic Metrics</h2>
    </div>
    <div class="toolbar-body">
      <IconField>
        <InputText
          :model-value="filter"
          size="small"
          placeholder="Filter metrics"
          data-testid="metric-filter"
          @update:model-value="onFilterChange"
        />
        <InputIcon>
          <Search :size="12" />
        </InputIcon>
      </IconField>
      <Paginator
        :rows="limit"
        :first="first"
        :totalRecords="total"
        :alwaysShow="false"
        @page="onPageChange"
      ></Paginator>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { PageState } from 'primevue'
import { IconField, InputIcon, InputText, Paginator } from 'primevue'
import { Search } from 'lucide-vue-next'

type Props = {
  limit: number
  total: number
  first: number
  filter: string
  showTitle: boolean
}

type Emits = {
  pageChange: [PageState]
  filterChange: [string]
}

defineProps<Props>()
const emits = defineEmits<Emits>()

function onPageChange(event: PageState) {
  emits('pageChange', event)
}

function onFilterChange(value: string | undefined) {
  emits('filterChange', value ?? '')
}
</script>

<style scoped>
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
}

.toolbar-body {
  display: flex;
  align-items: center;
  gap: 12px;
}

:deep(.p-iconfield .p-inputtext) {
  width: 100%;
}

.p-iconfield .p-inputtext:not(:last-child) {
  padding-inline-end: calc(var(--p-form-field-padding-x) + var(--p-icon-size));
}

:deep(.p-iconfield .p-inputicon:last-child) {
  inset-inline-end: 9px;
}
</style>
