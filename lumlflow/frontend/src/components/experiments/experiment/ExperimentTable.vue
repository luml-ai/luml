<template>
  <DataTable
    :value="experimentsStore.experiments"
    table-class="table-fixed"
    scrollable
    scrollHeight="calc(100vh - 310px)"
    :selection="experimentsStore.selectedExperiments"
    :virtualScrollerOptions="virtualScrollerOptions"
    @update:selection="experimentsStore.setSelectedExperiments"
  >
    <template #empty>
      <div class="text-center h-full flex items-center justify-center">
        No experiments groups found
      </div>
    </template>
    <Column selectionMode="multiple" class="w-[40px]"></Column>
    <Column
      v-if="showColumn('Experiment name')"
      field="name"
      header="Experiment name"
      class="w-[180px]"
    ></Column>
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
          <span>{{ new Date(slotProps.data.created_at).toLocaleString() }}</span>
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
        <span>{{ durationToText(slotProps.data.duration) }}</span>
      </template>
    </Column>
    <Column v-if="showColumn('Source')" field="source" header="Source" class="w-[180px]">
      <template #body="slotProps">
        <div class="flex items-center gap-2">
          <FileChartLine :size="14" color="var(--p-primary-color)" />
          <span>{{ slotProps.data.source }}</span>
        </div>
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
          <span>{{ slotProps.data.metrics[metric] || '-' }}</span>
        </template>
      </Column>
    </template>
  </DataTable>
</template>

<script setup lang="ts">
import type { Experiment } from '@/store/experiments/experiments.interface'
import { DataTable, Column, type VirtualScrollerProps } from 'primevue'
import { useExperimentsStore } from '@/store/experiments'
import { computed, watch } from 'vue'
import { Check, CircleX, FileChartLine, Timer } from 'lucide-vue-next'
import { durationToText } from '@/helpers/date'
import { CONSTANTS_COLUMNS } from './experiment.const'
import ColumnTags from '@/components/table/ColumnTags.vue'
import ColumnDescription from '@/components/table/ColumnDescription.vue'
import ExperimentModelsListColumn from './ExperimentModelsListColumn.vue'

const experimentsStore = useExperimentsStore()

const virtualScrollerOptions: VirtualScrollerProps = {
  lazy: true,
  itemSize: 58.75,
  scrollHeight: 'calc(100vh - 310px)',
}

const statusIconInfo = computed(() => (status: Experiment['status']) => {
  if (status === 'completed') return { icon: Check, color: 'var(--p-tag-success-color)' }
  if (status === 'active') return { icon: Timer, color: 'var(--p-tag-info-color)' }
  return { icon: CircleX, color: 'var(--p-tag-danger-color)' }
})

const metricsColumns = computed(() => {
  const metricsSet = experimentsStore.experiments.reduce((acc, experiment) => {
    Object.keys(experiment.metrics).forEach((metric) => {
      acc.add(metric)
    })
    return acc
  }, new Set<string>())
  return Array.from(metricsSet)
})

const showColumn = computed(() => (columnTitle: string) => {
  return experimentsStore.visibleColumns.includes(columnTitle)
})

watch(
  metricsColumns,
  (metricsColumns) => {
    experimentsStore.setTableColumns([...CONSTANTS_COLUMNS, ...metricsColumns])
    experimentsStore.setVisibleColumns([...CONSTANTS_COLUMNS, ...metricsColumns.slice(0, 20)])
  },
  { immediate: true },
)
</script>

<style scoped></style>
