<template>
  <div class="workspace-flow-page">
    <NotebookHeader class="mb-2" />
    <div
      class="grid gap-2"
      :class="{
        'grid-cols-[292px_1fr]': flowStore.isSidebarOpened,
        'grid-cols-[54px_1fr]': !flowStore.isSidebarOpened,
      }"
    >
      <NotebooksSidebar />
      <div>
        <NotebookToolbar class="mb-2" />
        <NotebookBaseView v-if="flowStore.viewMode === 'notebook'" />
        <NotebookCanvasView v-if="flowStore.viewMode === 'canvas'" />
      </div>
    </div>
    <ExpandedCell
      v-if="expandedCell"
      :cell="expandedCell"
      v-model:visible="isExpandedCellVisible"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, watch } from 'vue'
import { useRoute } from 'vue-router'
import { useFlowStore } from '@/store/flow'
import NotebookHeader from '@/components/notebooks/NotebookHeader.vue'
import NotebooksSidebar from '@/components/notebooks/NotebooksSidebar.vue'
import NotebookToolbar from '@/components/notebooks/NotebookToolbar.vue'
import NotebookBaseView from '@/components/notebooks/NotebookBaseView.vue'
import NotebookCanvasView from '@/components/notebooks/NotebookCanvasView.vue'
import ExpandedCell from '@/components/notebooks/cell/ExpandedCell.vue'

const route = useRoute()
const flowStore = useFlowStore()

const directory = computed(() =>
  typeof route.query.directory === 'string' ? route.query.directory : null,
)

watch(directory, (flow) => flowStore.setFlow(flow), { immediate: true })

onUnmounted(() => flowStore.reset())

const expandedCell = computed(
  () => flowStore.cells.find((cell) => cell.slug === flowStore.expandedCellId) ?? null,
)

const isExpandedCellVisible = computed({
  get: () => expandedCell.value !== null,
  set: (visible: boolean) => {
    if (!visible) flowStore.setExpandedCellId(null)
  },
})
</script>

<style scoped></style>
