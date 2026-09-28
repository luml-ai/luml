<template>
  <div class="flex flex-col gap-2 min-w-0">
    <p
      v-if="preview.newerFormatNote"
      class="inline-flex items-center gap-1.5 text-sm text-muted-color"
    >
      <Info :size="14" class="shrink-0" />
      {{ preview.newerFormatNote }}
    </p>
    <div class="overflow-auto" :class="bodyMaxClass(density)">
      <ConfigGrid :config="preview.entries" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'
import type { KvPreview } from '../model/types'
import ConfigGrid from './ConfigGrid.vue'
import { bodyMaxClass, type RenderDensity } from './shared'

defineProps<{
  preview: KvPreview
  density?: RenderDensity
}>()
</script>
