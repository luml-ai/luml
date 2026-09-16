<template>
  <div class="flex flex-col gap-3 nowheel nodrag">
    <template v-for="(block, index) in blocks" :key="index">
      <CellTableBlock v-if="block.block === 'table'" :block="block" />
      <CellLineChart v-else-if="block.block === 'series'" :block="block" />
      <CellPlotImage v-else-if="block.block === 'image'" :block="block" />
      <CellMarkdownBlock v-else-if="block.block === 'markdown'" :block="block" />
      <CellKeyValueBlock v-else-if="block.block === 'kv'" :block="block" />
      <CellFileBlock v-else :block="block" />
    </template>
    <p v-if="truncated" class="text-sm text-muted-color">Preview truncated.</p>
  </div>
</template>

<script setup lang="ts">
import type { CellPreviewBlocksProps } from './preview.interface'
import CellTableBlock from './CellTableBlock.vue'
import CellLineChart from './CellLineChart.vue'
import CellPlotImage from './CellPlotImage.vue'
import CellMarkdownBlock from './CellMarkdownBlock.vue'
import CellKeyValueBlock from './CellKeyValueBlock.vue'
import CellFileBlock from './CellFileBlock.vue'

defineProps<CellPreviewBlocksProps>()
</script>

<style scoped></style>
