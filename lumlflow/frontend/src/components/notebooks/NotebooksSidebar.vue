<template>
  <div>
    <NotebookMainInfo class="mb-2" />
    <NotebookSidebarAccordion v-if="flowStore.isSidebarOpened" />
    <div v-else class="card">
      <SidebarTooltipPlug
        v-for="section in sections"
        :key="section.value"
        :icon="section.icon"
        :label="section.label"
        :tooltip="
          section.count === undefined ? section.label : `${section.label} (${section.count})`
        "
      />
    </div>
  </div>
</template>

<script setup lang="ts">
import { useFlowStore } from '@/store/flow'
import NotebookMainInfo from '@/components/notebooks/NotebookMainInfo.vue'
import NotebookSidebarAccordion from '@/components/notebooks/sidebar-accordion/NotebookSidebarAccordion.vue'
import SidebarTooltipPlug from '@/components/notebooks/SidebarTooltipPlug.vue'
import { useSidebarSections } from '@/components/notebooks/sidebar-accordion/useSidebarSections'

const flowStore = useFlowStore()
const sections = useSidebarSections()
</script>

<style scoped>
@reference "@/assets/css/index.css";

.card {
  @apply bg-(--p-card-background) border border-surface rounded-lg overflow-hidden;
}
</style>
