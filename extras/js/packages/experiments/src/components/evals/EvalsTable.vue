<template>
  <EvalsToolbar
    v-model:search="searchModel"
    :columns="allColumns"
    :selected-columns="selectedColumns"
    scrollable
    :export-loading="exportLoading"
    @edit="setSelectedColumns"
    @export="exportCSV"
  ></EvalsToolbar>
  <div class="table-wrapper">
    <DataTable
      ref="tableRef"
      :value="tableData"
      show-gridlines
      row-group-mode="rowspan"
      :group-rows-by="isMultipleModels ? 'id' : undefined"
      sort-mode="single"
      export-filename="experiment_snapshot"
      :scrollable="useScroll"
      :scroll-height="useScroll ? '410px' : undefined"
      :virtual-scroller-options="useScroll ? virtualScrollerOptions : undefined"
      striped-rows
      lazy
      class="evals-table"
      tableStyle="table-layout: fixed;"
      data-key="id"
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
                v-if="column.title.startsWith('feedback')"
                class="header-cell-content"
                @click="toggleSubheader"
              >
                <component
                  v-if="columnIcon('feedback')"
                  :is="columnIcon('feedback')"
                  :size="16"
                  color="var(--p-primary-500)"
                ></component>
                <span class="header-cell-title">
                  {{ column.title }}
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
            v-for="item in visibleChildren"
            :key="item.key"
            :pt="{
              headerCell: {
                class: {
                  'children-with-left-border': childrenWithLeftBorder.includes(item.key),
                  'bottom-border': true,
                },
              },
            }"
            :sort-field="item.label"
            :sortable="isSortableColumn(item.key)"
          >
            <template #header>
              <span v-tooltip.top="item.label" class="cell header-cell">
                {{ item.label }}
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
              <div v-if="isFeedbackColumn(column)">
                <FeedbackSubheader
                  :annotation-name="column"
                  :feedback="annotationsSummary.feedback"
                ></FeedbackSubheader>
              </div>
            </template>
          </Column>
        </Row>
      </ColumnGroup>
      <Column v-for="column in visibleColumns" :key="column" :field="column">
        <template #body="slotProps">
          <ModelIdColumn
            v-if="column === 'modelId'"
            :data="modelsInfo[slotProps.data.modelId]"
          ></ModelIdColumn>
          <button
            v-else-if="column === 'id'"
            class="cell link"
            v-tooltip.top="slotProps.data[column]"
            @click="showTraces(slotProps.data)"
          >
            {{ slotProps.data[column] }}
          </button>
          <FeedbackColumn
            v-else-if="slotProps.data[column]?.isFeedbackColumn"
            :data="slotProps.data[column]"
          ></FeedbackColumn>
          <ExpectationColumn
            v-else-if="slotProps.data[column]?.isExpectationColumn"
            :data="slotProps.data[column]"
          ></ExpectationColumn>
          <CellWithTooltip v-else :value="slotProps.data[column]"></CellWithTooltip>
        </template>
      </Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import type { TableEmits, TableProps } from './evals.interface'
import { DataTable, ColumnGroup, Row, Column, type VirtualScrollerLazyEvent } from 'primevue'
import { computed, nextTick, ref, watch } from 'vue'
import { useEvalsStore } from '../../store/evals'
import { useEvalsTable } from '@/hooks/useEvalsTable'
import { COLUMNS_ICONS, COLUMNS_TITLES_MAP } from '@/constants/tables'
import { ChevronDown, ChevronUp } from 'lucide-vue-next'
import EvalsToolbar from './EvalsToolbar.vue'
import FeedbackSubheader from './FeedbackSubheader.vue'
import ModelIdColumn from '../table/model-id-column/ModelIdColumn.vue'
import FeedbackColumn from '../table/feedback-column/FeedbackColumn.vue'
import ExpectationColumn from '../table/ecpectation-column/ExpectationColumn.vue'
import CellWithTooltip from '../table/cell-with-tooltip/CellWithTooltip.vue'

const props = defineProps<TableProps>()

const emit = defineEmits<TableEmits>()

const searchModel = defineModel<string>('search', { default: '' })

const evalsStore = useEvalsStore()

const {
  exportCSV,
  exportLoading,
  setSelectedColumns,
  selectedColumns,
  data: tableData,
  sortParams,
  onSort,
} = useEvalsTable(
  computed(() => props.data),
  searchModel,
  props.datasetId,
  computed(() => visibleColumns.value),
)

const tableRef = ref()
const isSubheaderVisible = ref(false)

const isMultipleModels = computed(() => {
  return Object.keys(props.modelsInfo).length > 1
})

const scoresColumns = computed(() => {
  return props.columnsTree.find((column) => column.title === 'scores')?.children || []
})

const isSortableColumn = computed(() => (columnName: string) => {
  return scoresColumns.value.includes(columnName)
})

const getParentColumnWidth = computed(() => (columnName: string, childrenLength: number) => {
  if (columnName === 'modelId') {
    return 140 + 'px'
  }
  if (columnName.startsWith('feedback')) {
    return childrenLength * 194 + 'px'
  }
  if (columnName === 'refs') {
    return childrenLength * 140 + 'px'
  }
  if (columnName.startsWith('expectation')) {
    return childrenLength * 194 + 'px'
  }
  return childrenLength * 110 + 'px'
})

const useScroll = computed(() => tableData.value.length > 8)

const virtualScrollerOptions = {
  itemSize: 44,
  lazy: true,
  onLazyLoad: onLazyLoad,
}

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

const formattedTree = computed(() => {
  return sortedTree.value.map((item) => {
    const isFeedback = item.title.startsWith('feedback')
    const isExpectation = item.title.startsWith('expectation')
    if (isFeedback) {
      return {
        title: item.title,
        children: item.children?.map((child) => child + ' (feedback)'),
      }
    }
    if (isExpectation) {
      return {
        title: item.title,
        children: item.children?.map((child) => child + ' (expectation)'),
      }
    }
    return item
  })
})

const allColumns = computed(() => {
  const columnsSet = formattedTree.value.reduce((acc, column) => {
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
  return formattedTree.value
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
  return visibleTree.value.reduce((acc: { key: string; label: string }[], column) => {
    const children = column.children || []
    const objects = children.map((columnName) => {
      let label = columnName
      if (column.title.startsWith('feedback')) {
        label = label.replace(' (feedback)', '')
      } else if (column.title.startsWith('expectation')) {
        label = label.replace(' (expectation)', '')
      }
      return {
        key: columnName,
        label,
      }
    })
    acc = [...acc, ...objects]
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
  return visibleTree.value.find((column) => column.title.startsWith('feedback'))?.children || []
})

const isFeedbackColumn = computed(() => (columnName: string) => {
  return visibleFeedbackColumns.value.includes(columnName)
})

const isFirstFeedbackColumn = computed(() => (columnName: string) => {
  return visibleFeedbackColumns.value.indexOf(columnName) === 0
})

const isLastFeedbackColumn = computed(() => (columnName: string) => {
  return (
    visibleFeedbackColumns.value.indexOf(columnName) === visibleFeedbackColumns.value.length - 1
  )
})

function showTraces(data: Record<string, any>) {
  const { dataset_id, id } = data
  const allModelsData = props.data.filter(
    (item) => item.dataset_id === dataset_id && item.id === id,
  )
  evalsStore.setCurrentEvalData(allModelsData)
}

function toggleSubheader() {
  isSubheaderVisible.value = !isSubheaderVisible.value
}

watch(
  () => props.data.length,
  () => {
    nextTick(() => {
      tableRef.value?.virtualScroller?.refresh()
    })
  },
)

watch(
  () => sortParams.value,
  () => {
    emit('sort', sortParams.value)
  },
)
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

:deep(td) {
  height: 44px;
}
</style>
