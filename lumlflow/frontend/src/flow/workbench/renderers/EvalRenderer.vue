<template>
  <div class="flex flex-col gap-3 min-w-0">
    <div class="grid grid-cols-[repeat(auto-fit,minmax(6.5rem,1fr))] gap-2">
      <div
        v-for="(value, name) in preview.scores"
        :key="name"
        class="rounded-lg border border-surface-200 dark:border-surface-700 px-3 py-2"
      >
        <p class="text-2xl font-medium tabular-nums leading-tight">{{ formatMetric(value) }}</p>
        <p class="text-sm text-muted-color mt-0.5">{{ name }}</p>
      </div>
    </div>
    <p class="text-sm text-muted-color">
      <code class="font-mono">{{ preview.datasetRef }}</code>
      · {{ preview.sampleCount.toLocaleString() }} samples
    </p>
  </div>
</template>

<script setup lang="ts">
import { formatMetric } from '../model/format'
import type { EvalPreview } from '../model/types'
import type { RenderDensity } from './shared'

defineProps<{
  preview: EvalPreview
  density?: RenderDensity
}>()
</script>
