<template>
  <NotebookAccordionAssetsList :list="items" />
</template>

<script setup lang="ts">
import { computed } from 'vue'
import { useFlowStore } from '@/store/flow'
import NotebookAccordionAssetsList from '@/components/notebooks/sidebar-accordion/NotebookAccordionAssetsList.vue'

const flowStore = useFlowStore()

const items = computed(() => flowStore.notebookCells.filter((cell) => cell.type === 'model'))
</script>

<style scoped></style>
