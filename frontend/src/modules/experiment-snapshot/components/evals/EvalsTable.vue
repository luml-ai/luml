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
      :value="data"
      show-gridlines
      rowGroupMode="rowspan"
      groupRowsBy="id"
      sortMode="single"
      sortField="id"
      :sortOrder="1"
      export-filename="experiment_snapshot"
      scrollHeight="400px"
      :virtualScrollerOptions="{ itemSize: 45.5 }"
      class="evals-table"
      :tableStyle="
        visibleColumns.length < MIN_COLUMNS_FOR_FIXED_LAYOUT ? 'table-layout: fixed;' : ''
      "
    >
      <ColumnGroup type="header">
        <Row>
          <template v-for="column in visibleTree">
            <Column
              v-if="isParentColumnVisible(column)"
              :header="column.title === 'modelId' ? 'Model name' : column.title"
              :rowspan="column.children?.length ? 1 : 2"
              :colspan="column.children?.length ? column.children.length : 1"
              :field="column.title"
              :pt="{
                headerCell: 'header-cell-parent',
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
          </template>
        </Row>
        <Row>
          <Column
            v-for="children in visibleChildren"
            :header="children"
            :pt="{
              headerCell: childrenWithLeftBorder.includes(children)
                ? 'children-with-left-border'
                : '',
              columnTitle: {
                style: 'width: 88px; overflow: hidden; text-overflow: ellipsis;',
              },
            }"
          >
          </Column>
        </Row>
      </ColumnGroup>
      <template v-for="column in visibleColumns">
        <Column :field="column">
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
              @click="showTraces(slotProps.data.dataset_id, slotProps.data.id)"
            >
              {{ slotProps.data[column] }}
            </button>
            <div
              v-else
              v-tooltip.top="`${slotProps.data[column]}`"
              class="cell"
              :style="visibleColumns.length < MIN_COLUMNS_FOR_FIXED_LAYOUT ? '' : 'width: 88px;'"
            >
              {{ slotProps.data[column] }}
            </div>
          </template>
        </Column>
      </template>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { DataTable, ColumnGroup, Row, Column } from 'primevue'
import { computed, ref } from 'vue'
import { CircleArrowDown, CircleArrowUp, FileText, ChartBar } from 'lucide-vue-next'
import EvalsToolbar from './EvalsToolbar.vue'
import type { ModelsInfo } from '../../interfaces/interfaces'
import { useEvalsStore } from '../../store/evals'

const MIN_COLUMNS_FOR_FIXED_LAYOUT = 7

export interface EvalsTableColumn {
  title: string
  children?: string[]
}

type Props = {
  columnsTree: EvalsTableColumn[]
  data: Record<string, any>[]
  modelsInfo: ModelsInfo
}

const props = defineProps<Props>()

const evalsStore = useEvalsStore()

const tableRef = ref()
const selectedColumns = ref<string[]>([])

const sortedTree = computed(() => {
  return props.columnsTree.sort((a, b) => {
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
  return Array.from(columnsSet).filter((column) => {
    if (column === 'dataset_id') return false
    if (column === 'modelId') {
      return Object.keys(props.modelsInfo).length > 1
    }
    return true
  })
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
  if (columnName.toLowerCase() === 'inputs') {
    return CircleArrowDown
  } else if (columnName.toLowerCase() === 'outputs') {
    return CircleArrowUp
  } else if (columnName.toLowerCase() === 'refs') {
    return FileText
  } else if (columnName.toLowerCase() === 'scores') {
    return ChartBar
  } else return null
})

const isParentColumnVisible = computed(() => (column: EvalsTableColumn) => {
  if (column.children) {
    return !!column.children.find((child) => visibleColumns.value.includes(child))
  } else {
    return visibleColumns.value.includes(column.title)
  }
})

function setSelectedColumns(columns: string[]) {
  selectedColumns.value = columns
}

function showTraces(datasetId: string, evalId: string) {
  evalsStore.setCurrentEvalData(datasetId, evalId)
}

function exportTable() {
  if (!tableRef.value) {
    console.error('Table for export was not found')
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

:deep(.p-datatable-column-sorted) .cell {
  width: 123px;
}

.link {
  text-decoration: underline;
}
</style>
