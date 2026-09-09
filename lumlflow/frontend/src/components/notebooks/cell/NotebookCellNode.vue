<template>
  <NotebookCell class="w-[400px]">
    <NotebookCellTabs v-model="activeTab" class="mb-4" />
    <NotebookPlot v-if="activeTab === 'plot'" />
    <NotebookCode v-if="activeTab === 'code'" />
    <NotebookLogs v-if="activeTab === 'logs'" />
  </NotebookCell>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import NotebookCell from '@/components/notebooks/cell/NotebookCell.vue'
import NotebookCellTabs from '@/components/notebooks/cell/NotebookCellTabs.vue'
import NotebookPlot from '@/components/notebooks/cell/NotebookPlot.vue'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'

const activeTab = ref('plot')
</script>

<style scoped></style>
