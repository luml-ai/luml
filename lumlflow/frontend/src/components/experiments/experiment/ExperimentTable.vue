<template>
  <DataTable
    :value="experimentsStore.experiments"
    table-class="table-fixed"
    scrollable
    scrollHeight="calc(100vh - 320px)"
    :selection="experimentsStore.selectedExperiments"
    :virtualScrollerOptions="virtualScrollerOptions"
    :loading="loading"
    :pt="{
      emptyMessage: loading ? 'hidden' : '',
    }"
    @row-click="onRowClick"
    @update:selection="experimentsStore.setSelectedExperiments"
  >
    <template #empty>
      <div class="text-center h-full flex items-center justify-center max-w-[calc(100vw-40px)]">
        No experiments found.
      </div>
    </template>
    <Column selectionMode="multiple" class="w-[40px]"></Column>
    <Column
      v-if="showColumn('Experiment name')"
      field="name"
      header="Experiment name"
      class="w-[180px]"
    >
      <template #body="slotProps">
        <div v-tooltip.top="slotProps.data.name.length > 14 ? slotProps.data.name : null">
          {{ cutStringOnMiddle(slotProps.data.name, 14) }}
        </div>
      </template></Column
    >
    <Column
      v-if="showColumn('Creation time')"
      field="created_at"
      header="Creation time"
      class="w-[215px]"
    >
      <template #body="slotProps">
        <div class="flex items-center gap-2">
          <component
            :is="statusIconInfo(slotProps.data.status).icon"
            :size="14"
            :color="statusIconInfo(slotProps.data.status).color"
          />
          <span>{{ dateToText(slotProps.data.created_at) }}</span>
        </div>
      </template>
    </Column>
    <Column
      v-if="showColumn('Description')"
      field="description"
      header="Description"
      class="w-[302px]"
    >
      <template #body="slotProps">
        <ColumnDescription :description="slotProps.data.description" />
      </template>
    </Column>
    <Column v-if="showColumn('Tags')" field="tags" header="Tags" class="w-[215px]">
      <template #body="slotProps">
        <ColumnTags :tags="slotProps.data.tags || []" :width="180" />
      </template>
    </Column>
    <Column v-if="showColumn('Duration')" field="duration" header="Duration" class="w-[126px]">
      <template #body="slotProps">
        <span
          v-if="typeof slotProps.data.duration === 'number'"
          v-tooltip.top="durationToText(slotProps.data.duration)"
          class="line-clamp-1 overflow-hidden text-ellipsis"
        >
          {{ durationToText(slotProps.data.duration) }}
        </span>
        <span v-else>-</span>
      </template>
    </Column>
    <Column v-if="showColumn('Source')" field="source" header="Source" class="w-[180px]">
      <template #body="slotProps">
        <div v-if="slotProps.data.source" class="flex items-center gap-2">
          <FileChartLine :size="14" color="var(--p-primary-color)" />
          <span>{{ slotProps.data.source }}</span>
        </div>
        <span v-else>-</span>
      </template>
    </Column>
    <Column v-if="showColumn('Models')" field="models" header="Models" class="w-[180px]">
      <template #body="slotProps">
        <ExperimentModelsListColumn :models="slotProps.data.models" />
      </template>
    </Column>
    <template v-for="metric in metricsColumns" :key="metric">
      <Column v-if="showColumn(metric)" :field="metric" :header="metric" class="w-[180px]">
        <template #body="slotProps">
          <span
            v-tooltip.top="
              slotProps.data.dynamic_params?.[metric]
                ? String(slotProps.data.dynamic_params?.[metric])
                : null
            "
            class="line-clamp-1 overflow-hidden text-ellipsis"
          >
            {{ slotProps.data.dynamic_params?.[metric] || '-' }}
          </span>
        </template>
      </Column>
    </template>
  </DataTable>
</template>

<script setup lang="ts">
import { DataTable, Column, type VirtualScrollerProps, type DataTableRowClickEvent } from 'primevue'
import { useExperimentsStore } from '@/store/experiments'
import { useGroupsStore } from '@/store/groups'
import { computed, onBeforeUnmount, ref, watch } from 'vue'
import { FileChartLine } from 'lucide-vue-next'
import { dateToText, durationToText } from '@/helpers/date'
import { CONSTANTS_COLUMNS, getStatusIconInfo } from './experiment.const'
import ColumnTags from '@/components/table/ColumnTags.vue'
import ColumnDescription from '@/components/table/ColumnDescription.vue'
import ExperimentModelsListColumn from './ExperimentModelsListColumn.vue'
import { cutStringOnMiddle } from '@/helpers/string'
import { ROUTE_NAMES } from '@/router/router.const'
import { useRouter } from 'vue-router'

interface Props {
  groupId: string
}

const props = defineProps<Props>()

const experimentsStore = useExperimentsStore()
const groupsStore = useGroupsStore()
const router = useRouter()

const loading = ref(true)

const virtualScrollerOptions: VirtualScrollerProps = {
  lazy: true,
  itemSize: 64,
  scrollHeight: 'calc(100vh - 310px)',
}

const statusIconInfo = computed(() => getStatusIconInfo)

const metricsColumns = computed(() => {
  return groupsStore.detailedGroup?.experiments_dynamic_params || []
})

const showColumn = computed(() => (columnTitle: string) => {
  return experimentsStore.visibleColumns.includes(columnTitle)
})

function onRowClick(event: DataTableRowClickEvent) {
  const target = event.originalEvent.target as HTMLElement
  const rowIncludeCheckbox = !!target.querySelector('input[type="checkbox"]')
  if (rowIncludeCheckbox) return
  const id = event.data.id
  if (!id) return
  router.push({
    name: ROUTE_NAMES.EXPERIMENT_OVERVIEW,
    params: { groupId: props.groupId, experimentId: String(id) },
  })
}

watch(
  metricsColumns,
  (metricsColumns) => {
    experimentsStore.setTableColumns([...CONSTANTS_COLUMNS, ...metricsColumns])
    experimentsStore.setVisibleColumns([...CONSTANTS_COLUMNS, ...metricsColumns.slice(0, 20)])
  },
  { immediate: true },
)

watch(
  () => props.groupId,
  (groupId) => {
    experimentsStore.setQueryParams({
      ...experimentsStore.queryParams,
      group_id: groupId,
    })
  },
  { immediate: true },
)

watch(
  () => experimentsStore.experiments,
  () => {
    loading.value = false
  },
)

onBeforeUnmount(() => {
  experimentsStore.reset()
})
</script>

<style scoped></style>
