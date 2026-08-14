<template>
  <component :is="renderer" :preview="preview" :density="density" />
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
}>()

const renderer = computed(() => rendererForPreview(props.preview))
</script>
