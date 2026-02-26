<template>
  <div class="grid grid-cols-2 gap-6">
    <div>
      <div class="mb-5">
        <h3 class="text-lg mb-4">Parameters ({{ parameters.length }})</h3>
        <Card>
          <template #content>
            <IconField class="mb-2">
              <InputText v-model="parametersSearch" placeholder="Search" size="small" fluid />
              <InputIcon>
                <Search :size="12" />
              </InputIcon>
            </IconField>
            <DataTable
              :value="visibleParameters"
              table-class="table-fixed"
              scrollable
              scrollHeight="200px"
            >
              <template #empty>
                <div class="flex justify-center items-center h-full">
                  <span>No parameters found</span>
                </div>
              </template>
              <Column field="name" header="Parameter"></Column>
              <Column field="value" header="Value"></Column>
            </DataTable>
          </template>
        </Card>
      </div>
      <div class="mb-5">
        <h3 class="text-lg mb-4">Metrics ({{ metrics.length }})</h3>
        <Card>
          <template #content>
            <IconField class="mb-2">
              <InputText v-model="metricsSearch" placeholder="Search" size="small" fluid />
              <InputIcon>
                <Search :size="12" />
              </InputIcon>
            </IconField>
            <DataTable
              :value="visibleMetrics"
              table-class="table-fixed"
              scrollable
              scrollHeight="200px"
            >
              <template #empty>
                <div class="flex justify-center items-center h-full">
                  <span>No metrics found</span>
                </div>
              </template>
              <Column field="name" header="Metric"></Column>
              <Column field="value" header="Value"></Column>
            </DataTable>
          </template>
        </Card>
      </div>
      <div class="mb-5">
        <h3 class="text-lg mb-4">Logged models ({{ models.length }})</h3>
        <Card>
          <template #content>
            <DataTable :value="models" table-class="table-fixed" scrollable scrollHeight="200px">
              <template #empty>
                <div class="flex justify-center items-center h-full">
                  <span>No models found</span>
                </div>
              </template>
              <Column field="name" header="Model name">
                <template #body="slotProps">
                  <div class="flex items-center gap-2">
                    <CircuitBoardIcon :size="14" color="var(--p-primary-color)" />
                    <span>{{ slotProps.data.name }}</span>
                  </div>
                </template>
              </Column>
              <Column field="size" header="Size"></Column>
              <Column field="created_at" header="Creation time"></Column>
            </DataTable>
          </template>
        </Card>
      </div>
    </div>
    <div>
      <h3 class="text-lg mb-4">About this experiment</h3>
      <Card>
        <template #content>
          <div class="flex flex-col gap-4 mb-7">
            <div class="grid grid-cols-[100px_1fr] gap-6 items-center">
              <span>Experiment ID</span>
              <div class="flex items-center gap-2">
                <span>{{ cutStringOnMiddle(experiment.id, 8) }}</span>
                <Copy
                  :size="12"
                  color="var(--p-button-text-secondary-color)"
                  class="cursor-pointer"
                  @click="copyExperimentId"
                />
              </div>
            </div>
            <div class="grid grid-cols-[100px_1fr] gap-6 items-center">
              <span>Status</span>
              <div>
                <Tag v-if="experimentStatusInfo" :severity="experimentStatusInfo.severity">
                  <component
                    :size="12"
                    :is="experimentStatusInfo.icon"
                    :color="experimentStatusInfo.color"
                  />
                  <span>{{ experimentStatusInfo.text }}</span>
                </Tag>
              </div>
            </div>
            <div class="grid grid-cols-[100px_1fr] gap-6 items-center">
              <span>Creation time</span>
              <div>{{ dateToText(experiment.created_at) }}</div>
            </div>
            <div class="grid grid-cols-[100px_1fr] gap-6">
              <span>Description</span>
              <div>{{ experiment.description || '-' }}</div>
            </div>
            <div class="grid grid-cols-[100px_1fr] gap-6 items-center">
              <span>Tags</span>
              <div class="flex flex-wrap gap-1">
                <Tag v-for="tag in tags" :key="tag">{{ tag }}</Tag>
              </div>
            </div>
            <div class="grid grid-cols-[100px_1fr] gap-6 items-center">
              <span>Duration</span>
              <div v-if="typeof experiment.duration === 'number'">
                {{ durationToText(experiment.duration || 0) }}
              </div>
              <div v-else>-</div>
            </div>
            <div class="grid grid-cols-[100px_1fr] gap-6 items-center">
              <span>Source</span>
              <div v-if="experiment.source" class="flex items-center gap-1">
                <FileChartLine :size="12" color="var(--p-primary-color)" />
                <span>{{ experiment.source }}</span>
              </div>
              <div v-else>-</div>
            </div>
          </div>
          <UploadModal />
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Card, IconField, InputText, InputIcon, DataTable, Column, Tag } from 'primevue'
import {
  Search,
  CircuitBoardIcon,
  Copy,
  FileChartLine,
  Check,
  Timer,
  CircleX,
} from 'lucide-vue-next'
import UploadModal from '@/components/upload/UploadModal.vue'
import { dateToText, durationToText } from '@/helpers/date'
import { cutStringOnMiddle, getSizeText } from '@/helpers/string'
import { useExperimentStore } from '@/store/experiment'
import { computed, ref } from 'vue'
import { useToast } from 'primevue'
import { successToast } from '@/toasts'

const experimentStore = useExperimentStore()
const toast = useToast()

const parametersSearch = ref('')
const metricsSearch = ref('')

const experiment = computed(() => {
  if (!experimentStore.experiment) throw new Error('Experiment not found')
  return experimentStore.experiment
})

const parameters = computed(() => {
  if (!experiment.value?.static_params) return []
  return Object.entries(experiment.value.static_params).map(([name, value]) => ({
    name,
    value,
  }))
})

const visibleParameters = computed(() => {
  return parameters.value.filter((parameter) => parameter.name.includes(parametersSearch.value))
})

const metrics = computed(() => {
  if (!experiment.value?.dynamic_params) return []
  return Object.entries(experiment.value.dynamic_params).map(([name, value]) => ({
    name,
    value,
  }))
})

const visibleMetrics = computed(() => {
  return metrics.value.filter((metric) => metric.name.includes(metricsSearch.value))
})

const models = computed(() => {
  if (!experiment.value?.models) return []
  return experiment.value.models.map((model) => ({
    name: model.name,
    size: getSizeText(model.size || 0),
    created_at: dateToText(model.created_at),
  }))
})

const tags = computed(() => {
  return experiment.value?.tags || []
})

const experimentStatusInfo = computed(() => {
  if (!experiment.value) return null
  else if (experiment.value.status === 'completed')
    return {
      icon: Check,
      color: 'var(--p-tag-success-color)',
      text: 'Completed',
      severity: 'success',
    }
  else if (experiment.value.status === 'active')
    return { icon: Timer, color: 'var(--p-tag-info-color)', text: 'Active', severity: 'info' }
  else
    return { icon: CircleX, color: 'var(--p-tag-danger-color)', text: 'Failed', severity: 'danger' }
})

function copyExperimentId() {
  navigator.clipboard.writeText(experiment.value.id)
  toast.add(successToast('Experiment ID copied to clipboard'))
}
</script>

<style scoped></style>
