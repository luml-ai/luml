<template>
  <div class="table-wrapper">
    <DataTable
      ref="tableRef"
      :value="tableData"
      show-gridlines
      sort-mode="single"
      :scrollable="useScroll"
      :scroll-height="useScroll ? '410px' : undefined"
      :virtual-scroller-options="useScroll ? virtualScrollerOptions : undefined"
      striped-rows
      lazy
      tableStyle="table-layout: fixed;"
      data-key="trace_id"
      class="traces-table"
      @sort="onSort"
    >
      <template #empty>No traces found...</template>
      <ColumnGroup type="header">
        <Row>
          <Column
            v-if="selectedColumns.includes('trace_id')"
            field="trace_id"
            header="ID"
            style="width: 120px"
            :rowspan="2"
            :pt="{
              headerCell: {
                class: 'border-top-none',
              },
            }"
          ></Column>
          <Column
            v-if="selectedColumns.includes('execution_time')"
            field="execution_time"
            header="execution time"
            sortable
            style="width: 155px"
            :rowspan="2"
            :pt="{
              headerCell: {
                class: 'border-top-none',
              },
            }"
          ></Column>
          <Column
            v-if="selectedColumns.includes('state')"
            field="state"
            header="state"
            style="width: 120px"
            :rowspan="2"
            :pt="{
              headerCell: {
                class: 'border-top-none',
              },
            }"
          ></Column>
          <Column
            v-if="selectedColumns.includes('span_count')"
            field="span_count"
            header="spans"
            style="width: 100px"
            :rowspan="2"
            :pt="{
              headerCell: {
                class: 'border-top-none',
              },
            }"
          ></Column>
          <Column
            v-if="visibleFeedbackColumns.length > 0"
            :pt="{
              headerCell: {
                class: 'border-bottom-none border-top-none',
              },
            }"
            :style="{
              width: feedbackWidth,
            }"
            :colspan="visibleFeedbackColumns.length"
          >
            <template #header>
              <button @click="toggleSubheader" class="header-cell-content">
                <Smile :size="16" color="var(--p-primary-color)" />
                <span class="header-cell-title"
                  >feedback ({{ visibleFeedbackColumns.length }})</span
                >
                <div class="header-cell-dropdown-icon">
                  <component
                    :is="isSubheaderVisible ? ChevronUp : ChevronDown"
                    :size="16"
                    color="var(--p-datatable-row-toggle-button-color)"
                  />
                </div>
              </button>
            </template>
          </Column>
          <Column
            v-if="visibleExpectationColumns.length > 0"
            :pt="{
              headerCell: {
                class: 'border-bottom-none border-top-none',
              },
            }"
            :style="{
              width: expectationWidth,
            }"
            :colspan="visibleExpectationColumns.length"
          >
            <template #header>
              <Target :size="16" color="var(--p-primary-color)" />
              <span>expectation ({{ visibleExpectationColumns.length }})</span>
            </template>
          </Column>
          <Column
            v-if="selectedColumns.includes('evals')"
            field="evals"
            style="width: 100px"
            :rowspan="2"
            :pt="{
              headerCell: {
                class: 'border-top-none',
              },
            }"
          >
            <template #header>
              <Braces :size="16" color="var(--p-primary-color)" />
              <span>evals</span>
            </template>
          </Column>
          <Column
            v-if="selectedColumns.includes('created_at')"
            field="created_at"
            header="creation time"
            sortable
            style="width: 176px"
            :rowspan="2"
            :pt="{
              headerCell: {
                class: 'border-top-none',
              },
            }"
          ></Column>
        </Row>
        <Row>
          <Column
            v-for="column in [...visibleFeedbackColumns, ...visibleExpectationColumns]"
            :key="column"
            :field="column"
            :pt="{
              headerCell: {
                class: {
                  'border-left-none':
                    column !== visibleFeedbackColumns[0] && column !== visibleExpectationColumns[0],
                  'border-right-none': true,
                  'border-top-none': true,
                },
              },
            }"
          >
            <template #header>
              <div v-tooltip.top="column" class="child-header-content">
                {{ column }}
              </div>
            </template>
          </Column>
        </Row>
        <Row v-if="isSubheaderVisible && visibleFeedbackColumns.length > 0">
          <Column
            v-for="column in selectedColumns"
            :key="column"
            :pt="{
              headerCell: {
                class: {
                  'border-top-none': true,
                  'border-left-none': !showColumnLeftBorder(column),
                },
              },
            }"
          >
            <template #header>
              <div v-if="visibleFeedbackColumns.includes(column)">
                <FeedbackSubheader
                  :annotation-name="column"
                  :feedback="annotationsSummary.feedback"
                ></FeedbackSubheader>
              </div>
            </template>
          </Column>
        </Row>
      </ColumnGroup>
      <Column v-if="selectedColumns.includes('trace_id')" field="trace_id" header="ID">
        <template #body="slotProps">
          <button class="link cell" @click="showTrace(slotProps.data.trace_id)">
            {{ slotProps.data.trace_id }}
          </button>
        </template>
      </Column>
      <Column
        v-if="selectedColumns.includes('execution_time')"
        field="execution_time"
        header="execution time"
      >
        <template #body="slotProps">
          <span v-tooltip.top="getFormattedExecutionTime(slotProps.data.execution_time)">
            {{ getFormattedExecutionTime(slotProps.data.execution_time) }}
          </span>
        </template>
      </Column>
      <Column v-if="selectedColumns.includes('state')" field="state" header="state">
        <template #body="slotProps">
          <span>
            {{ TRACE_STATE_MAP[slotProps.data.state as keyof typeof TRACE_STATE_MAP] }}
          </span>
        </template>
      </Column>
      <Column
        v-if="selectedColumns.includes('span_count')"
        field="span_count"
        header="spans"
      ></Column>
      <Column
        v-for="column in visibleFeedbackColumns"
        :key="column"
        :field="column"
        :pt="{
          bodyCell: {
            class: {
              'border-left-none': !showColumnLeftBorder(column),
            },
          },
        }"
      >
        <template #body="slotProps">
          <FeedbackColumn :data="slotProps.data[column]"></FeedbackColumn>
        </template>
      </Column>
      <Column
        v-for="column in visibleExpectationColumns"
        :key="column"
        :field="column"
        :pt="{
          bodyCell: {
            class: {
              'border-left-none': !showColumnLeftBorder(column),
            },
          },
        }"
      >
        <template #body="slotProps">
          <ExpectationColumn :data="slotProps.data[column]"></ExpectationColumn>
        </template>
      </Column>
      <Column v-if="selectedColumns.includes('evals')" field="evals" header="evals">
        <template #body="slotProps">
          <div v-if="slotProps.data.evals?.length === 0">-</div>
          <button
            v-else
            v-for="item in slotProps.data.evals"
            :key="item"
            class="link cell"
            @click="showEval(item)"
          >
            {{ item }}
          </button>
        </template>
      </Column>
      <Column
        v-if="selectedColumns.includes('created_at')"
        field="created_at"
        header="creation time"
      ></Column>
    </DataTable>
  </div>
</template>

<script setup lang="ts">
import { Braces, ChevronDown, ChevronUp, Smile, Target } from 'lucide-vue-next'
import {
  DataTable,
  Column,
  ColumnGroup,
  Row,
  type VirtualScrollerLazyEvent,
  type DataTableSortEvent,
  type VirtualScrollerProps,
  useToast,
} from 'primevue'
import type { TableEmits, TableProps } from './traces.interface'
import type { FeedbackColumnData } from '../table/feedback-column/interface'
import type { ExpectationColumnData } from '../table/ecpectation-column/interface'
import { computed, ref } from 'vue'
import { getErrorMessage, getFormattedExecutionTime } from '@/helpers/helpers'
import { TRACE_STATE_MAP } from './traces.const'
import { useEvalsStore } from '@/store/evals'
import { simpleErrorToast } from '@/lib/primevue/data/toasts'
import { watch } from 'vue'
import { nextTick } from 'vue'
import FeedbackSubheader from '../evals/FeedbackSubheader.vue'
import FeedbackColumn from '../table/feedback-column/FeedbackColumn.vue'
import ExpectationColumn from '../table/ecpectation-column/ExpectationColumn.vue'

const props = defineProps<TableProps>()
const emit = defineEmits<TableEmits>()

const evalsStore = useEvalsStore()
const toast = useToast()

const tableRef = ref()
const isSubheaderVisible = ref(false)

const tableData = computed(() => {
  return props.data.map((trace) => {
    const feedbackObject =
      trace.annotations?.feedback.reduce(
        (acc, item) => {
          acc[item.name] = {
            isFeedbackColumn: true,
            positiveCount: item.counts['true'] ?? 0,
            negativeCount: item.counts['false'] ?? 0,
          }
          return acc
        },
        {} as Record<string, FeedbackColumnData & { isFeedbackColumn: true }>,
      ) ?? {}

    const expectationObject =
      trace.annotations?.expectations.reduce(
        (acc, item) => {
          acc[item.name] = {
            isExpectationColumn: true,
            total: item.total,
            positive: item.positive,
            negative: item.negative,
            firstValue: item.firstValue,
          }
          return acc
        },
        {} as Record<string, ExpectationColumnData & { isExpectationColumn: true }>,
      ) ?? {}
    return {
      ...trace,
      ...feedbackObject,
      ...expectationObject,
    }
  })
})

const visibleFeedbackColumns = computed(() => {
  return props.annotationsSummary.feedback
    .map((item) => item.name)
    .filter((column) => props.selectedColumns.includes(column))
})

const visibleExpectationColumns = computed(() => {
  return props.annotationsSummary.expectations
    .map((item) => item.name)
    .filter((column) => props.selectedColumns.includes(column))
})

const feedbackWidth = computed(() => {
  return visibleFeedbackColumns.value.length * 194 + 'px'
})

const expectationWidth = computed(() => {
  return visibleExpectationColumns.value.length * 300 + 'px'
})

const showColumnLeftBorder = computed(() => (columnName: string) => {
  const firstVisibleFeedbackColumn = visibleFeedbackColumns.value[0]
  if (columnName === firstVisibleFeedbackColumn) return true
  const lastVisibleFeedbackColumn =
    visibleFeedbackColumns.value[visibleFeedbackColumns.value.length - 1]
  const lastVisibleFeedbackColumnIndex = props.selectedColumns.findIndex(
    (column) => column === lastVisibleFeedbackColumn,
  )
  if (lastVisibleFeedbackColumnIndex === -1) return false
  const columnWithLeftBorder = props.selectedColumns[lastVisibleFeedbackColumnIndex + 1]
  return columnName === columnWithLeftBorder
})

const useScroll = computed(() => props.data.length > 8)

const virtualScrollerOptions: VirtualScrollerProps = {
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

function onSort(event: DataTableSortEvent) {
  const { sortField, sortOrder } = event
  emit('sort', { sortField: sortField as string, sortOrder: sortOrder === 1 ? 'asc' : 'desc' })
}

async function showEval(evalId: string) {
  try {
    const evalData = await evalsStore.getProvider.getEvalById(props.artifactId, evalId)
    evalsStore.setCurrentEvalData([evalData])
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  }
}

async function showTrace(traceId: string) {
  try {
    const snapsTree = await evalsStore.getTraceSpansTree(props.artifactId, traceId)
    evalsStore.setSelectedTrace(snapsTree, props.artifactId)
  } catch (error) {
    toast.add(simpleErrorToast(getErrorMessage(error)))
  }
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
</script>

<style scoped>
.table-wrapper {
  overflow: hidden;
}

.traces-table {
  margin-left: -1px;
  margin-right: -1px;
}

:deep(.p-datatable-table) {
  font-size: 14px;
}

:deep(.p-datatable-column-header-content) {
  font-weight: var(--p-datatable-column-title-font-weight);
}

:deep(.p-datatable-column-header-content svg) {
  flex: 0 0 auto;
}

:deep(.border-bottom-none) {
  border-bottom: transparent;
}

:deep(.border-top-none) {
  border-top: transparent;
}

:deep(.border-left-none) {
  border-left: transparent;
}

:deep(.border-right-none) {
  border-right: transparent;
}

.child-header-content {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.link {
  cursor: pointer;
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

:deep(td) {
  height: 44px;
}
</style>
