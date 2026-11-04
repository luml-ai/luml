<template>
  <NotebookAccordionAssetsList :list="flowStore.notebookCells" show-icons />
</template>

<script setup lang="ts">
import { useFlowStore } from '@/store/flow'
import NotebookAccordionAssetsList from '@/components/notebooks/sidebar-accordion/NotebookAccordionAssetsList.vue'

const flowStore = useFlowStore()
</script>

<style scoped></style>
