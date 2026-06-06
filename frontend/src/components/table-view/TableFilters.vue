<template>
  <d-overlay-badge v-if="filters.length" :value="filters.length">
    <d-button severity="secondary" rounded variant="outlined" @click="toggleFilter">
      <span class="button-label">Filter</span>
      <Filter width="14" height="14" />
    </d-button>
  </d-overlay-badge>
  <d-button v-else severity="secondary" rounded variant="outlined" @click="toggleFilter">
    <span class="button-label">Filter</span>
    <Filter width="14" height="14" />
  </d-button>
  <d-popover ref="filterPopover">
    <div class="popover-wrapper" :style="{ width: '39.9rem' }">
      <div class="filters-list">
        <div v-for="filter in currentFilters" :key="filter.id" class="filter-item">
          <d-select placeholder="Column" :options="columnSelectOptions" v-model="filter.column" />
          <d-select
            placeholder="Operator"
            :options="getFilterTypeSelectOptions(filter.column)"
            v-model="filter.filterType"
          />
          <d-input-text
            class="input"
            placeholder="Value"
            v-model="filter.parameter"
            :type="getInputType(filter.column)"
          />
          <d-button
            v-if="currentFilters.length > 1"
            severity="secondary"
            variant="outlined"
            @click="deleteFilter(filter.id)"
          >
            <template #icon>
              <Trash2 width="14" height="14" />
            </template>
          </d-button>
        </div>
      </div>
      <d-divider />
      <div class="popover-footer">
        <d-button label="Add filter" variant="text" @click="addMoreFilter">
          <template #icon>
            <Plus width="14" height="14" />
          </template>
        </d-button>
        <div class="popover-footer-buttons">
          <d-button label="clear" severity="secondary" variant="outlined" @click="clear" />
          <d-button label="apply" severity="secondary" @click="apply" />
        </div>
      </div>
    </div>
  </d-popover>
</template>

<script setup lang="ts">
import type { ColumnType } from '@/hooks/useDataTable'
import { computed, ref } from 'vue'
import { FilterType, type FilterItem } from '@/lib/data-table/interfaces'
import { Filter, Plus, Trash2 } from 'lucide-vue-next'

export type FilterDataItem = {
  name: string
  type: 'number' | 'string'
}

type Props = {
  data: FilterDataItem[]
  filters: FilterItem[]
  columnTypes: Record<string, ColumnType>
}

type Emits = {
  (event: 'apply', filters: FilterItem[]): void
}

const props = defineProps<Props>()
const emit = defineEmits<Emits>()
const filterPopover = ref()
const currentFilters = ref<FilterItem[]>(getCurrentFilters())

const columnSelectOptions = computed(() => {
  const filterAcc = props.filters.reduce((acc, filter) => {
    if (!acc.includes(filter.column)) acc.push(filter.column)
    return acc
  }, [] as string[])
  props.data.forEach((item) => {
    if (!filterAcc.includes(item.name)) filterAcc.push(item.name)
  })

  return filterAcc
})
const getFilterTypeSelectOptions = computed(() => (column: string) => {
  const columnType = props.columnTypes[column]
  switch (columnType) {
    case undefined:
      return []
    case 'number':
      return [
        FilterType.Equals,
        FilterType.NotEquals,
        FilterType.LessThan,
        FilterType.LessThanOrEqualTo,
        FilterType.GreaterThan,
        FilterType.GreaterThanOrEqualTo,
      ]
    default:
      return [FilterType.Equals, FilterType.NotEquals]
  }
})
const getInputType = computed(() => (column: string) => {
  const columnType = props.data.find((item) => item.name === column)?.type
  switch (columnType) {
    case 'number':
      return 'number'
    default:
      return 'string'
  }
})

function getCurrentFilters() {
  return props.filters.length
    ? JSON.parse(JSON.stringify(props.filters))
    : [
        {
          id: 1,
          column: '',
          filterType: FilterType.Equals,
          parameter: '',
        },
      ]
}
function toggleFilter(event: Event) {
  filterPopover.value.toggle(event)
}
function deleteFilter(id: number) {
  currentFilters.value = currentFilters.value.filter((filter) => filter.id !== id)
}
function addMoreFilter() {
  currentFilters.value.push({
    id: currentFilters.value.length + 1,
    column: '',
    filterType: FilterType.Equals,
    parameter: '',
  })
}
function clear() {
  currentFilters.value = [
    {
      id: 1,
      column: '',
      filterType: FilterType.Equals,
      parameter: '',
    },
  ]
  emit('apply', [])
  filterPopover.value.toggle()
}
function apply() {
  const availableFilters = currentFilters.value.filter(
    (filter) => filter.column && filter.filterType && filter.parameter,
  )
  emit('apply', JSON.parse(JSON.stringify(availableFilters)))
  filterPopover.value.toggle()
}
</script>

<style scoped>
.popover-wrapper {
  padding: 1.5rem;
  width: 639px;
  max-width: calc(100vw - 24px);
}

.popover-footer {
  display: flex;
  align-items: center;
  justify-content: space-between;
}

.popover-footer-buttons {
  display: flex;
  gap: 12px;
}

.filters-list {
  display: flex;
  flex-direction: column;
  gap: 1rem;
}

.filter-item {
  display: grid;
  grid-template-columns: repeat(3, 1fr) 35px;
  gap: 0.5rem;
}

.input {
  width: 100%;
}

@media (max-width: 768px) {
  .button-label {
    display: none;
  }
  .popover-wrapper {
    padding: 0;
    padding-top: 8px;
  }
  .filter-item {
    grid-template-columns: 35px 1fr 1fr 35px;
  }
  .filter-item:not(:last-child) {
    padding-bottom: 15px;
    border-bottom: 1px solid var(--p-divider-border-color);
  }
  .filter-item > *:nth-child(1) {
    grid-column: span 2;
  }
  .filter-item > *:nth-child(2) {
    grid-column: span 2;
  }
  .filter-item > *:nth-child(3) {
    grid-column: span 3;
  }
}
</style>
