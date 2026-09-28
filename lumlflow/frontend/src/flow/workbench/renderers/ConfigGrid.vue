<template>
  <dl class="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1">
    <template v-for="(value, key) in config" :key="key">
      <dt class="font-mono text-sm leading-5 text-muted-color">{{ key }}</dt>
      <dd class="font-mono text-sm leading-5 tabular-nums break-all">{{ render(value) }}</dd>
    </template>
  </dl>
</template>

<script setup lang="ts">
import { formatMetric, type MetricValue } from '../model/format'
import type { ParamValue } from '../model/types'
import { formatParam } from './shared'

const props = defineProps<{ config: Record<string, ParamValue>; metrics?: boolean }>()

function render(value: ParamValue): string {
  if (props.metrics && isMetric(value)) return formatMetric(value)
  return formatParam(value)
}

function isMetric(value: ParamValue): value is MetricValue {
  return typeof value === 'number' || value === 'nan' || value === 'inf' || value === '-inf'
}
</script>
