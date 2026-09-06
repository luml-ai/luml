<template>
  <NotebookAccordionAssetsList :list="items" show-icons />
</template>

<script setup lang="ts">
import { ref } from 'vue'
import type { NotebookAssetInterface } from '@/components/notebooks/notebooks.interface'
import NotebookAccordionAssetsList from '@/components/notebooks/sidebar-accordion/NotebookAccordionAssetsList.vue'

const items = ref<NotebookAssetInterface[]>([
  {
    id: '1',
    type: 'graph',
    name: 'correlation_heatmap',
    unmaterialized: false,
  },
  {
    id: '2',
    type: 'graph',
    name: 'eda',
    unmaterialized: false,
  },
  {
    id: '3',
    type: 'experiment',
    name: 'evaluate',
    unmaterialized: false,
  },

  {
    id: '4',
    type: 'graph',
    name: ' feature_distributions',
    unmaterialized: false,
  },
  {
    id: '5',
    type: 'dataset',
    name: 'load_data',
    unmaterialized: false,
  },
  {
    id: '6',
    type: 'graph',
    name: 'prediction_diagnostics',
    unmaterialized: false,
  },
  {
    id: '7',
    type: 'dataset',
    name: 'split',
    unmaterialized: false,
  },
  {
    id: '8',
    type: 'graph',
    name: 'train_model',
    unmaterialized: false,
  },
  {
    id: '9',
    type: 'model',
    name: 'train_model',
    unmaterialized: false,
  },
  {
    id: '10',
    type: 'unknown',
    name: 'untitled_1_asdasdsadasd dsadasdasdas asdsadasd Dsadasdasdd',
    unmaterialized: true,
  },
])
</script>

<style scoped></style>
