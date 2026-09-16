<template>
  <p v-if="content.status === 'loading'" class="text-sm text-muted-color">Loading…</p>
  <p v-else-if="content.status === 'error'" class="text-sm text-muted-color">
    {{ content.message }}
  </p>
  <CellPreviewBlocks
    v-else-if="content.status === 'ready'"
    :blocks="content.blocks"
    :truncated="content.truncated"
  />
</template>

<script setup lang="ts">
import type { CellOutputTabContentProps } from './preview.interface'
import CellPreviewBlocks from './CellPreviewBlocks.vue'

defineProps<CellOutputTabContentProps>()
</script>

<style scoped></style>
