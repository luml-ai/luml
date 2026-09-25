<template>
  <component
    :is="renderer"
    :preview="preview"
    :density="density"
    v-bind="downloadProps"
  />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { PreviewValue } from '../model/types'
import { rendererForPreview } from './registry'

/**
 * Dispatches a stored preview to the renderer registered for its kind.
 * Renderers are display-only: no emits; links out (tracker refs) render as
 * plain anchors. `density` lets a renderer tighten itself for canvas cards
 * vs. the notebook column vs. the expand drawer.
 */
const props = defineProps<{
  preview: PreviewValue
  density?: 'canvas' | 'notebook' | 'drawer'
  downloadUrl?: string
}>()

const renderer = computed(() => rendererForPreview(props.preview))
const downloadProps = computed(() =>
  props.preview.type === 'file' || props.preview.type === 'blocks'
    ? { downloadUrl: props.downloadUrl }
    : {},
)
</script>
