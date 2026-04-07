<template>
  <div class="toolbar">
    <div class="left">
      <IconField class="icon-field">
        <InputIcon class="search-icon">
          <Search :size="12" />
        </InputIcon>
        <InputText
          v-model="searchModel"
          placeholder="Search traces"
          size="small"
          fluid
          class="search-input"
        />
      </IconField>
    </div>
    <div class="right">
      <TableFilter
        :fields="visibleTypedColumns"
        :async-validate-callback="asyncValidateCallback"
        @apply="filterChange"
      />
      <TableEditColumns
        :button-icon="Bolt"
        :columns="columns"
        :rounded-button="false"
        :selected-columns="selectedColumns"
        :disabled-columns="['id']"
        @edit="(data) => $emit('edit', data)"
      ></TableEditColumns>
      <Button severity="secondary" variant="outlined" size="small" @click="$emit('export')">
        <span>Export CSV</span>
        <Download :size="14"></Download>
      </Button>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { ToolbarEmits, ToolbarProps } from './traces.interface'
import type { FilterItem } from '../table/filter/filter.interface'
import type { TypedColumnInfo } from '@/interfaces/interfaces'
import { computed } from 'vue'
import { Button, IconField, InputIcon, InputText } from 'primevue'
import { Bolt, Download, Search } from 'lucide-vue-next'
import { useTraceStore } from '@/store/trace'
import TableEditColumns from '../table/TableEditColumns.vue'
import TableFilter from '../table/filter/TableFilter.vue'
import { useEvalsStore } from '@/store/evals'

const evalStore = useEvalsStore()
const traceStore = useTraceStore()

defineProps<ToolbarProps>()
const emit = defineEmits<ToolbarEmits>()

const searchModel = defineModel<string>('search', { default: '' })

const visibleTypedColumns = computed<TypedColumnInfo[]>(() => {
  return [
    { name: 'state', type: 'string' },
    { name: 'evals', type: 'string' },
    { name: 'execution_time', type: 'number' },
    { name: 'span_count', type: 'number' },
    { name: 'created_at', type: 'string' },
    ...traceStore.typedColumnsList,
  ]
})

async function asyncValidateCallback(filters: FilterItem[]) {
  const filtersStrings = createFiltersString(filters)
  const results = await evalStore.getProvider.validateTracesFilter(filtersStrings)
  return results
}

function filterChange(filters: FilterItem[]) {
  const filtersStrings = createFiltersString(filters)
  emit('filters-change', filtersStrings)
}

function createFiltersString(filters: FilterItem[]) {
  return filters.map((filter) => `${filter.field} ${filter.operator} ${filter.value}`)
}
</script>

<style scoped>
.toolbar {
  padding: 0 0 12px;
  display: flex;
  justify-content: space-between;
  gap: 20px;
}

.left {
  flex: 1 1;
}

.right {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.icon-field {
  max-width: 280px;
  width: 100%;
}

.search-input {
  padding-left: 30px !important;
}

.search-icon {
  inset-inline-start: 9px !important;
}
</style>
