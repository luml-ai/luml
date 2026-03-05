<template>
  <EvalsToolbar
    :columns="allColumns"
    :selected-columns="selectedColumns"
    scrollable
    @edit="setSelectedColumns"
    @export="exportTable"
  ></EvalsToolbar>
  <div class="table-wrapper">
    <DataTable
      ref="tableRef"
      :value="flatData"
      show-gridlines
      rowGroupMode="rowspan"
      groupRowsBy="id"
      sortMode="single"
      sortField="id"
      :sortOrder="1"
      export-filename="experiment_snapshot"
      scrollable
      :scrollHeight="tableHeight"
      :virtualScrollerOptions="virtualScrollerOptions"
      class="evals-table"
      tableStyle="table-layout: fixed;"
    >
      <template #empty>No evals found...</template>
      <ColumnGroup type="header">
        <Row>
          <Column
            v-for="column in visibleTree"
            :key="column.title"
            :header="column.title === 'modelId' ? 'Model name' : column.title"
            :rowspan="column.children?.length ? 1 : 2"
            :colspan="column.children?.length ? column.children.length : 1"
            :field="column.title"
            :pt="{
              headerCell: {
                class: 'header-cell-parent',
                width: (column.children?.length || 1) * 110 + 'px',
              },
            }"
          >
            <template #header>
              <component
                v-if="columnIcon(column.title)"
                :is="columnIcon(column.title)"
                :size="16"
                color="var(--p-primary-500)"
              ></component>
            </template>
          </Column>
        </Row>
        <Row>
          <Column
            v-for="children in visibleChildren"
            :key="children"
            :pt="{
              headerCell: {
                class: childrenWithLeftBorder.includes(children) ? 'children-with-left-border' : '',
              },
            }"
          >
            <template #header>
              <span v-tooltip.top="children" class="cell" style="width: 88px">
                {{ children }}
              </span>
            </template>
          </Column>
        </Row>
      </ColumnGroup>
      <Column v-for="column in visibleColumns" :key="column" :field="column">
        <template #body="slotProps">
          <div
            v-if="column === 'modelId'"
            v-tooltip.top="modelsInfo[slotProps.data[column]]?.name"
            class="cell"
            style="width: 123px"
          >
            <span
              class="circle"
              :style="{ backgroundColor: modelsInfo[slotProps.data[column]]?.color }"
            ></span>
            {{ modelsInfo[slotProps.data[column]]?.name }}
          </div>
          <button
            v-else-if="column === 'id'"
            class="cell link"
            v-tooltip.top="slotProps.data[column]"
            @click="showTraces(slotProps.data)"
          >
            {{ slotProps.data[column] }}
          </button>
          <div v-else v-tooltip.top="String(slotProps.data[column])" class="cell">
            {{ slotProps.data[column] }}
          </div>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import type { EvalsInfo, ModelsInfo } from '../../interfaces/interfaces'
import {
  DataTable,
  ColumnGroup,
  Row,
  Column,
  useToast,
  type VirtualScrollerLazyEvent,
} from 'primevue'
import { computed, ref } from 'vue'
import { useEvalsStore } from '../../store/evals'
import { COLUMNS_ICONS } from '@/constants/tables'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import EvalsToolbar from './EvalsToolbar.vue'

interface Emits {
  (e: 'get-next-page'): void
}

const emit = defineEmits<Emits>()

const toast = useToast()

export interface EvalsTableColumn {
  title: string
  children?: string[]
}

type Props = {
  columnsTree: EvalsTableColumn[]
  data: EvalsInfo[]
  modelsInfo: ModelsInfo
  tableHeight: string
}

const props = defineProps<Props>()

const evalsStore = useEvalsStore()

const tableRef = ref()
const selectedColumns = ref<string[]>([])

const flatData = computed(() => {
  return props.data.map((item) => {
    const entries = Object.entries(item)
    return entries.reduce((acc: Record<string, any>, [key, value]) => {
      if (typeof value === 'object') {
        Object.entries(value).map((child) => {
          const childKey = child[0]
          const childValue = child[1]
          acc[childKey] = childValue
        })
      } else {
        acc[key] = value
      }
      return acc
    }, {})
  })
})

const virtualScrollerOptions = computed(() => {
  if (props.data.length < 15) return
  return {
    itemSize: 44,
    lazy: true,
    onLazyLoad: onLazyLoad,
  }
})

function onLazyLoad(event: VirtualScrollerLazyEvent) {
  const { last } = event
  if (last >= props.data.length) {
    emit('get-next-page')
  }
}

const sortedTree = computed(() => {
  return [...props.columnsTree].sort((a, b) => {
    const order = ['id', 'modelId']
    const indexA = order.indexOf(a.title)
    const indexB = order.indexOf(b.title)
    const weightA = indexA === -1 ? Infinity : indexA
    const weightB = indexB === -1 ? Infinity : indexB
    return weightA - weightB
  })
})

const allColumns = computed(() => {
  const columnsSet = sortedTree.value.reduce((acc, column) => {
    if (column.children) {
      column.children.map((child) => acc.add(child))
    } else {
      acc.add(column.title)
    }
    return acc
  }, new Set<string>())
  columnsSet.delete('dataset_id')
  const isSingleArtifact = Object.keys(props.modelsInfo).length === 1
  if (isSingleArtifact) columnsSet.delete('modelId')
  return Array.from(columnsSet)
})

const visibleColumns = computed(() => {
  return selectedColumns.value.length ? selectedColumns.value : allColumns.value
})

const visibleTree = computed(() => {
  return sortedTree.value
    .map((column) => {
      if (column.children) {
        const filteredChildren = column.children.filter((child) =>
          visibleColumns.value.includes(child),
        )
        if (!filteredChildren.length) return null
        return { title: column.title, children: filteredChildren }
      } else {
        const show = visibleColumns.value.includes(column.title)
        return show ? column : null
      }
    })
    .filter((column) => !!column)
})

const visibleChildren = computed(() => {
  return visibleTree.value.reduce((acc: string[], column) => {
    const children = column.children ? column.children : []
    acc = [...acc, ...children]
    return acc
  }, [])
})

const childrenWithLeftBorder = computed(() => {
  return visibleTree.value.map((column) => column.children?.[0]).filter((children) => !!children)
})

const columnIcon = computed(() => (columnName: string) => {
  const lowerCaseColumnName = columnName.toLowerCase()
  if (lowerCaseColumnName in COLUMNS_ICONS) {
    return COLUMNS_ICONS[lowerCaseColumnName as keyof typeof COLUMNS_ICONS]
  }
  return null
})

function setSelectedColumns(columns: string[]) {
  selectedColumns.value = columns
}

function showTraces(data: Record<string, any>) {
  const { dataset_id, id } = data
  const allModelsData = props.data.filter(
    (item) => item.dataset_id === dataset_id && item.id === id,
  )
  evalsStore.setCurrentEvalData(allModelsData)
}

function exportTable() {
  if (!tableRef.value) {
    toast.add(simpleErrorToast('Table for export was not found'))
  } else {
    tableRef.value.exportCSV()
  }
}
</script>

<style scoped>
.cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.table-wrapper {
  overflow: hidden;
}

.evals-table {
  margin-left: -1px;
  margin-right: -1px;
  font-size: 14px;
}

.evals-table :deep(th) {
  border: none;
}

.evals-table :deep(tbody tr:first-child td) {
  border-top: 1px solid var(--p-datatable-body-cell-border-color) !important;
}

.evals-table :deep(td:first-child) {
  border-left: none;
}

.evals-table :deep(tbody td:first-child) {
  border-left: 1px solid var(--p-datatable-body-cell-border-color);
}

:deep(.header-cell-parent:not(:first-child)) {
  border-left: 1px solid var(--p-datatable-body-cell-border-color);
}

.evals-table :deep(.children-with-left-border) {
  border-left: 1px solid var(--p-datatable-body-cell-border-color);
}

.circle {
  display: inline-block;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  flex: 0 0 auto;
  margin-bottom: -2px;
}

:deep(.p-datatable-column-sorted) {
  background: var(--p-datatable-header-cell-background);
  color: var(--p-datatable-header-cell-color);
}

.link {
  text-decoration: underline;
}
</style>
