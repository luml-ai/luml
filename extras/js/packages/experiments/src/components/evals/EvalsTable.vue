<template>
  <EvalsToolbar
    v-model:search="searchModel"
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
      row-group-mode="rowspan"
      :group-rows-by="isMultipleModels ? 'id' : undefined"
      sort-mode="single"
      export-filename="experiment_snapshot"
      scrollable
      scroll-height="392px"
      :virtual-scroller-options="virtualScrollerOptions"
      striped-rows
      lazy
      class="evals-table"
      tableStyle="table-layout: fixed;"
      @sort="onSort"
    >
      <template #empty>No evals found...</template>
      <ColumnGroup type="header">
        <Row>
          <Column
            v-for="column in visibleTree"
            :key="column.title"
            :rowspan="column.children?.length ? 1 : 2"
            :colspan="column.children?.length ? column.children.length : 1"
            :field="column.title"
            :sort-field="column.title"
            :sortable="isSortableColumn(column.title)"
            :pt="{
              headerCell: {
                class: {
                  'header-cell-parent': true,
                  'bottom-border': !column.children?.length,
                },
                style: {
                  width: getParentColumnWidth(column.title, column.children?.length || 1),
                },
              },
            }"
          >
            <template #header>
              <button
                v-if="column.title === 'feedback'"
                class="header-cell-content"
                @click="toggleSubheader"
              >
                <component
                  v-if="columnIcon(column.title)"
                  :is="columnIcon(column.title)"
                  :size="16"
                  color="var(--p-primary-500)"
                ></component>
                <span class="header-cell-title">
                  {{ COLUMNS_TITLES_MAP['feedback'] }}
                </span>
                <div class="header-cell-dropdown-icon">
                  <component
                    :is="isSubheaderVisible ? ChevronUp : ChevronDown"
                    :size="16"
                    color="var(--p-datatable-row-toggle-button-color)"
                  />
                </div>
              </button>
              <div v-else class="header-cell-content">
                <component
                  v-if="columnIcon(column.title)"
                  :is="columnIcon(column.title)"
                  :size="16"
                  color="var(--p-primary-500)"
                ></component>
                <span class="header-cell-title">
                  {{
                    COLUMNS_TITLES_MAP[column.title as keyof typeof COLUMNS_TITLES_MAP] ||
                    column.title
                  }}
                </span>
              </div>
            </template>
          </Column>
        </Row>
        <Row>
          <Column
            v-for="children in visibleChildren"
            :key="children"
            :pt="{
              headerCell: {
                class: {
                  'children-with-left-border': childrenWithLeftBorder.includes(children),
                  'bottom-border': true,
                },
              },
            }"
            :sort-field="children"
            :sortable="isSortableColumn(children)"
          >
            <template #header>
              <span v-tooltip.top="children" class="cell header-cell">
                {{ children }}
              </span>
            </template>
          </Column>
        </Row>
        <Row v-if="isSubheaderVisible">
          <Column
            v-for="column in visibleColumns"
            :key="column"
            :pt="{
              headerCell: {
                class: {
                  'left-border': isFirstFeedbackColumn(column),
                  'right-border': isLastFeedbackColumn(column),
                  'bottom-border': true,
                },
              },
            }"
          >
            <template #header>
              <div v-if="isFeedbackColumn(column)" class="feedback-subheader">
                <UiFeedbackResult :positive="true" :percentage="90"></UiFeedbackResult>
                <UiFeedbackResult :positive="false" :percentage="10"></UiFeedbackResult>
              </div>
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
          <div
            v-else-if="slotProps.data[column]"
            v-tooltip.top="String(slotProps.data[column])"
            class="cell"
          >
            {{ slotProps.data[column] }}
          </div>
          <div v-else>-</div>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import type { TableEmits, TableProps } from './evals.interface'
import {
  DataTable,
  ColumnGroup,
  Row,
  Column,
  useToast,
  type VirtualScrollerLazyEvent,
  type DataTableSortEvent,
} from 'primevue'
import { computed, ref } from 'vue'
import { useEvalsStore } from '../../store/evals'
import { COLUMNS_ICONS, COLUMNS_TITLES_MAP } from '@/constants/tables'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import EvalsToolbar from './EvalsToolbar.vue'
import UiFeedbackResult from '../ui/UiFeedbackResult.vue'

const toast = useToast()

const props = defineProps<TableProps>()

const emit = defineEmits<TableEmits>()

const searchModel = defineModel<string>('search', { default: '' })

const evalsStore = useEvalsStore()

const tableRef = ref()
const selectedColumns = ref<string[]>([])
const isSubheaderVisible = ref(false)

const isMultipleModels = computed(() => {
  return Object.keys(props.modelsInfo).length > 1
})

const scoresColumns = computed(() => {
  return props.columnsTree.find((column) => column.title === 'scores')?.children || []
})

const isSortableColumn = computed(() => (columnName: string) => {
  if (columnName === 'id') return true
  return scoresColumns.value.includes(columnName)
})

const getParentColumnWidth = computed(() => (columnName: string, childrenLength: number) => {
  if (columnName === 'modelId') {
    return 140 + 'px'
  }
  if (columnName === 'feedback') {
    return childrenLength * 140 + 'px'
  }
  if (columnName === 'refs') {
    return childrenLength * 140 + 'px'
  }
  if (columnName === 'expectation') {
    return childrenLength * 140 + 'px'
  }
  return childrenLength * 110 + 'px'
})

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
    itemSize: 41.5,
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

const visibleFeedbackColumns = computed(() => {
  return visibleTree.value.find((column) => column.title === 'feedback')?.children || []
})

const isFeedbackColumn = computed(() => (columnName: string) => {
  return visibleFeedbackColumns.value.includes(columnName)
})

const isFirstFeedbackColumn = computed(() => (columnName: string) => {
  console.log(visibleFeedbackColumns.value.indexOf(columnName))
  return visibleFeedbackColumns.value.indexOf(columnName) === 0
})

const isLastFeedbackColumn = computed(() => (columnName: string) => {
  return (
    visibleFeedbackColumns.value.indexOf(columnName) === visibleFeedbackColumns.value.length - 1
  )
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

function onSort(event: DataTableSortEvent) {
  const { sortField, sortOrder } = event
  emit('sort', { sortField: sortField as string, sortOrder: sortOrder === 1 ? 'asc' : 'desc' })
}

function toggleSubheader() {
  isSubheaderVisible.value = !isSubheaderVisible.value
}
</script>

<style scoped>
.cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.header-cell {
  font-weight: var(--p-datatable-column-title-font-weight);
}

.header-cell-content {
  font-weight: var(--p-datatable-column-title-font-weight);
  display: flex;
  gap: 7px;
  align-items: center;
  width: 100%;
  color: var(--p-datatable-header-cell-color);
  text-align: left;
}

button.header-cell-content {
  cursor: pointer;
}

:deep(.header-cell-content svg) {
  flex: 0 0 auto;
}

.header-cell-title {
  flex: 1 1 auto;
}

.header-cell-dropdown-icon {
  flex: 0 0 auto;
}

.feedback-subheader {
  display: flex;
  gap: 8px;
  flex-direction: column;
  gap: 16px;
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

.evals-table :deep(.left-border) {
  border-left: 1px solid var(--p-datatable-body-cell-border-color);
}

.evals-table :deep(.right-border) {
  position: relative;
}

.evals-table :deep(.right-border)::after {
  content: '';
  position: absolute;
  top: 0;
  right: -1px;
  width: 1px;
  height: 100%;
  background-color: var(--p-datatable-body-cell-border-color);
}

.evals-table :deep(.bottom-border) {
  border-bottom: 1px solid var(--p-datatable-body-cell-border-color);
}
</style>
