<template>
  <div class="grid grid-cols-2 gap-6">
    <div>
      <ParametersCard :parameters="parameters" />

      <MetricsCard :metrics="metrics" />

      <ModelsCard
        :models="experiment?.models || []"
        :group-id="experiment?.group_id || ''"
        :experiment-id="experiment?.id || ''"
      />
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
          <UploadModal :experiment-id="experiment.id" :models="experiment.models || []" />
        </template>
      </Card>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Card, Tag } from 'primevue'
import { Copy, FileChartLine, Check, Timer, CircleX } from 'lucide-vue-next'
import UploadModal from '@/components/upload/UploadModal.vue'
import { dateToText, durationToText } from '@/helpers/date'
import { cutStringOnMiddle } from '@/helpers/string'
import { useExperimentStore } from '@/store/experiment'
import { computed } from 'vue'
import { useToast } from 'primevue'
import { successToast } from '@/toasts'
import ParametersCard from '@/table-cards/ParametersCard.vue'
import MetricsCard from '@/table-cards/MetricsCard.vue'
import ModelsCard from '@/table-cards/ModelsCard.vue'

const experimentStore = useExperimentStore()
const toast = useToast()

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

const metrics = computed(() => {
  if (!experiment.value?.dynamic_params) return []
  return Object.entries(experiment.value.dynamic_params).map(([name, value]) => ({
    name,
    value,
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
