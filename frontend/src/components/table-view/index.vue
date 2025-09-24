<template>
  <div class="wrapper">
    <header class="header">
      <div class="header-left">
        <div class="header-info">
          Columns:
          <span>{{ columnsCount }}</span>
        </div>
        <div class="header-info">
          Rows:
          <span>{{ value.length }}</span>
        </div>
      </div>
      <div class="header-right">
        <table-input-outputs v-if="inputsOutputsColumns" :columns="inputsOutputsColumns" :column-types="columnTypes" :selected-columns="selectedColumns"/>
        <table-sort :columns="currentColumns" v-model:multiSortMeta="multiSortMeta" />
        <table-filters
          v-if="filters"
          :data="dataForFilters"
          :filters="filters"
          :column-types="columnTypes"
          @apply="(event) => $emit('changeFilters', event)"
        />
        <table-edit
          :columns="allColumns"
          :selected-columns="selectedColumns"
          :target="target"
          @edit="(event) => $emit('edit', event)"
        />
        <d-button severity="secondary" rounded variant="outlined" @click="exportCallback">
          <span class="button-label">Export</span>
          <CloudDownload width="14" height="14" />
        </d-button>
      </div>
    </header>
    <div :style="{ height: tableHeight + 'px' }">
      <DataTable
        v-if="value.length"
        :value="value"
        showGridlines
        stripedRows
        scrollable
        :scrollHeight="tableHeight + 'px'"
        :multiSortMeta="multiSortMeta"
        sortMode="multiple"
        :virtualScrollerOptions="{ itemSize: 31 }"
        size="small"
        :style="{ fontSize: '14px' }"
      >
        <Column
          v-for="column in currentColumns"
          :id="column"
          :field="column"
          style="min-width: 13rem"
        >
          <template #header>
            <table-column-header
              :values="value"
              :column="cutStringOnMiddle(column)"
              :group="group"
              :target="target"
              :column-type="columnTypes[column]"
              :show-menu="showColumnHeaderMenu"
              :inputs-outputs-columns="inputsOutputsColumns"
              @change-group="(event) => $emit('changeGroup', event)"
              @set-target="(event) => $emit('setTarget', event)"
            />
          </template>
        </Column>
      </DataTable>
      <div v-else class="placeholder">Values not found...</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import type { FilterDataItem } from './TableFilters.vue'
import type { FilterItem } from '@/lib/data-table/interfaces'
import type { ColumnType, PromptFusionColumn } from '@/hooks/useDataTable'
import TableSort from './TableSort.vue'
import TableFilters from './TableFilters.vue'
import TableEdit from './TableEdit.vue'
import TableColumnHeader from './TableColumnHeader.vue'
import TableInputOutputs from './TableInputOutputs.vue'
import { CloudDownload } from 'lucide-vue-next'
import { DataTable, Column } from 'primevue'
import { computed, onBeforeMount, onBeforeUnmount, ref } from 'vue'

import { cutStringOnMiddle } from '@/helpers/helpers'

type Props = {
  columnsCount: number
  rowsCount: number
  allColumns: string[]
  value: object[]
  target?: string
  group?: string[]
  selectedColumns: string[]
  exportCallback: Function
  filters?: FilterItem[]
  columnTypes: Record<string, ColumnType>
  showColumnHeaderMenu: boolean
  inputsOutputsColumns?: PromptFusionColumn[]
}

type Emits = {
  (event: 'edit', list: string[]): void
  (event: 'setTarget', column: string): void
  (event: 'changeGroup', column: string): void
  (event: 'changeFilters', filters: FilterItem[]): void
}

const props = defineProps<Props>()
defineEmits<Emits>()

const multiSortMeta = ref([])
const tableHeight = ref(0)

const currentColumns = computed(() => (props.value.length ? Object.keys(props.value[0]) : []))
const dataForFilters = computed(() => {
  const row = props.value[0]
  const data: FilterDataItem[] = []
  for (const key in row) {
    data.push({
      name: key,
      type: typeof row[key as keyof typeof row] === 'number' ? 'number' : 'string',
    })
  }
  return data
})

function calcTableHeight() {
  let minusValue = 0
  if (window.innerWidth > 992) minusValue = 305
  else if (window.innerWidth > 768) minusValue = 345
  else {
    minusValue = 300
  }
  tableHeight.value = document.documentElement.clientHeight - minusValue
}

onBeforeMount(() => {
  calcTableHeight()
  window.addEventListener('resize', calcTableHeight)
})

onBeforeUnmount(() => {
  window.removeEventListener('resize', calcTableHeight)
})
</script>

<style scoped>
.wrapper {
  padding: 12px;
  padding-bottom: 0;
  margin-bottom: 12px;
  background-color: var(--p-card-background);
  border-radius: 8px;
  overflow: hidden;
  border: 1px solid var(--p-content-border-color);
}

.header {
  display: flex;
  justify-content: space-between;
  gap: 20px;
  margin-bottom: 12px;
  align-items: center;
}

.header-left {
  display: flex;
}

.header-info {
  padding: 16px;
  gap: 8px;
  display: inline-flex;
  align-items: center;
  font-size: 14px;
}

.header-info span {
  font-weight: 600;
}

.header-right {
  display: flex;
  gap: 8px;
  justify-content: flex-end;
}

.placeholder {
  font-size: 2rem;
  text-align: center;
  height: 100%;
  display: flex;
  justify-content: center;
  align-items: center;
}

@media (min-width: 993px) {
  @media (max-width: 1200px) {
    .header-left {
      flex-direction: column;
      gap: 0.5rem;
    }

    .header-info {
      padding-top: 0;
      padding-bottom: 0;
    }
  }
}

@media (max-width: 992px) {
  .header {
    flex-direction: column;
    align-items: flex-start;
    gap: 0;
  }

  .header-right {
    align-self: flex-end;
    flex-wrap: wrap;
  }
}

@media (min-width: 768px) {
  .wrapper {
    margin: 0 -80px;
  }
}

@media (max-width: 768px) {
  .header-info {
    padding: 5px;
  }
  .button-label {
    display: none;
  }
}
</style>
