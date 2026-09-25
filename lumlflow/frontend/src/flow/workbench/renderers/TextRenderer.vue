<template>
  <div class="relative min-w-0">
    <pre
      class="font-mono text-sm leading-relaxed whitespace-pre-wrap overflow-auto"
      :class="bodyMaxClass(density)"
      >{{ preview.text }}</pre
    >
    <div
      v-if="clamped"
      class="pointer-events-none absolute inset-x-0 bottom-0 h-10 bg-gradient-to-t from-surface-0 dark:from-surface-900 to-transparent"
    />
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { TextPreview } from '../model/types'
import { bodyMaxClass, type RenderDensity } from './shared'

const props = defineProps<{
  preview: TextPreview
  density?: RenderDensity
}>()

const MAX_PX: Record<string, number> = { notebook: 176, drawer: 480, canvas: 224 }
const LINE_PX = 20

// Deterministic overflow estimate: the fade only appears when the text will
// clip, so short values never get a washed-out last line.
const clamped = computed(() => {
  const lines = props.preview.text.split('\n').length
  return lines * LINE_PX > MAX_PX[props.density ?? 'canvas']
})
</script>
