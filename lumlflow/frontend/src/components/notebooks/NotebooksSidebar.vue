<template>
  <div>
    <NotebookMainInfo class="mb-2" />
    <NotebookSidebarAccordion v-if="flowStore.isSidebarOpened" />
    <div v-else class="card">
      <SidebarTooltipPlug tooltip="What is this?" label="Cells" />
      <SidebarTooltipPlug tooltip="What is this?" label="Experiments" />
      <SidebarTooltipPlug tooltip="What is this?" label="Models" />
      <SidebarTooltipPlug tooltip="What is this?" label="Activities" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useFlowStore } from '@/store/flow'
import NotebookMainInfo from '@/components/notebooks/NotebookMainInfo.vue'
import NotebookSidebarAccordion from '@/components/notebooks/sidebar-accordion/NotebookSidebarAccordion.vue'
import SidebarTooltipPlug from '@/components/notebooks/SidebarTooltipPlug.vue'

const flowStore = useFlowStore()
</script>

<style scoped>
@reference "@/assets/css/index.css";

.card {
  @apply bg-(--p-card-background) border border-surface rounded-lg overflow-hidden;
}
</style>
