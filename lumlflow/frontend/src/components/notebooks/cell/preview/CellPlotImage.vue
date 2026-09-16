<template>
  <img :src="src" :alt="block.mime" class="plot-image" />
</template>

<script setup lang="ts">
import type { CellPlotImageProps } from './preview.interface'
import { computed } from 'vue'

const props = defineProps<CellPlotImageProps>()

const src = computed(() => `data:${props.block.mime};base64,${props.block.data}`)
</script>

<style scoped>
.plot-image {
  max-width: 100%;
  max-height: 260px;
  object-fit: contain;
}
</style>
