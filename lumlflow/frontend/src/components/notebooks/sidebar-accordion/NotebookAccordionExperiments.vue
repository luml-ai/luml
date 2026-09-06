<template>
  <NotebookAccordionAssetsList :list="items" />
</template>

<script setup lang="ts">
import type { NotebookAssetInterface } from '@/components/notebooks/notebooks.interface'
import { ref } from 'vue'
import NotebookAccordionAssetsList from '@/components/notebooks/sidebar-accordion/NotebookAccordionAssetsList.vue'

const items = ref<NotebookAssetInterface[]>([
  {
    id: '1',
    type: 'experiment',
    name: 'evaluate.metrics',
    unmaterialized: false,
  },
])
</script>

<style scoped></style>
