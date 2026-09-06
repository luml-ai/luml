<template>
  <div class="card">
    <NotebookCellHeader />
    <div class="py-4">
      <slot>
        <NotebookCellTabs v-model="activeTab" />
        <NotebookPlot v-if="activeTab === 'plot'" />
        <NotebookCode v-if="activeTab === 'code'" />
        <NotebookLogs v-if="activeTab === 'logs'" />
      </slot>
    </div>
    <NotebookCellFooter />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import NotebookCellHeader from '@/components/notebooks/cell/NotebookCellHeader.vue'
import NotebookCellFooter from '@/components/notebooks/cell/NotebookCellFooter.vue'
import NotebookCellTabs from '@/components/notebooks/cell/NotebookCellTabs.vue'
import NotebookPlot from '@/components/notebooks/cell/NotebookPlot.vue'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'

const activeTab = ref('plot')
</script>

<style scoped>
@reference "@/assets/css/index.css";

.card {
  @apply bg-(--p-card-background) border border-surface rounded-lg overflow-hidden p-5 shadow-(--p-card-shadow);
}
</style>
