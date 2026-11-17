<template>
  <UiCard :title="title">
    <template #header-left>
      <div class="header-left">
        <h3 class="card__title">{{ title }}</h3>
        <CircleAlert
          v-if="aggregationTooltip"
          :size="14"
          v-tooltip="aggregationTooltip"
          color="var(--p-badge-warn-background)"
        />
        <TriangleAlert
          v-if="errorTooltip"
          :size="14"
          v-tooltip="errorTooltip"
          color="var(--p-message-error-color)"
          data-testid="chart-error"
        />
      </div>
    </template>
    <template #header-right>
      <div class="header-right">
        <ProgressSpinner v-if="loading" class="header-spinner" stroke-width="6" />
        <Button severity="secondary" variant="text" @click="scaled = true">
          <template #icon>
            <Maximize2 :size="14" />
          </template>
        </Button>
      </div>
    </template>
    <UiScalable v-model="scaled" :title="title">
      <slot></slot>
      <template #scaled>
        <slot name="scaled"></slot>
      </template>
    </UiScalable>
  </UiCard>
</template>

<script setup lang="ts">
import { computed, ref, watch } from 'vue'
import { CircleAlert, Maximize2, TriangleAlert } from 'lucide-vue-next'
import { Button, ProgressSpinner } from 'primevue'
import UiCard from '../ui/UiCard.vue'
import UiScalable from '../ui/UiScalable.vue'

type Props = {
  title: string
  /** Shown as a small spinner: the chart keeps what it shows until the new data arrives. */
  loading: boolean
  /** Steps per bucket of the aggregated data on screen; null when nothing is aggregated. */
  aggregationSteps: number | null
  /** A failed read; the chart keeps showing what it has next to it. */
  error?: string | null
}

type Emits = {
  scale: []
}

const props = withDefaults(defineProps<Props>(), { error: null })
const emits = defineEmits<Emits>()

const scaled = ref(false)

const aggregationTooltip = computed(() => {
  if (props.aggregationSteps === null || props.aggregationSteps <= 1) return null
  const steps = props.aggregationSteps.toLocaleString('en-US')
  return `Each point is an average over up to ${steps} steps. Zoom in to see more detail.`
})

const errorTooltip = computed(() =>
  props.error ? `Some data could not be loaded. ${props.error}` : null,
)

watch(scaled, (val) => {
  if (val) emits('scale')
})
</script>

<style scoped>
.header-left {
  display: flex;
  align-items: center;
  gap: 8px;
  height: 39px;
}

.header-right {
  display: flex;
  align-items: center;
  gap: 4px;
}

.header-spinner {
  width: 16px;
  height: 16px;
}

.card__title {
  font-size: 20px;
}
</style>
