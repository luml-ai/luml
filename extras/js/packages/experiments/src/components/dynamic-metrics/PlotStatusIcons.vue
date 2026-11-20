<template>
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
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { CircleAlert, TriangleAlert } from 'lucide-vue-next'

type Props = {
  /** Steps per bucket of the aggregated data on screen; null when nothing is aggregated. */
  aggregationSteps: number | null
  /** A failed read; the chart keeps showing what it has next to it. */
  error: string | null
}

const props = defineProps<Props>()

const aggregationTooltip = computed(() => {
  if (props.aggregationSteps === null || props.aggregationSteps <= 1) return null
  const steps = props.aggregationSteps.toLocaleString('en-US')
  return `Each point is an average over up to ${steps} steps. Zoom in to see more detail.`
})

const errorTooltip = computed(() =>
  props.error ? `Some data could not be loaded. ${props.error}` : null,
)
</script>
