<template>
  <NotebookCell
    class="w-[400px]"
    :class="{ 'border-primary!': isSelected }"
    :title="asset.name"
    :icon="NOTEBOOK_ASSET_ICONS[asset.type]"
    :cost-seconds="cell.cost_seconds"
    :state="cell.state"
    :causes="cell.causes"
    :reused="cell.reused"
    :cell="cell"
  >
    <NotebookCellTabs v-model="activeTab" class="mb-4" />
    <NotebookPlot v-if="activeTab === 'plot'" />
    <NotebookCode v-if="activeTab === 'code'" />
    <NotebookLogs v-if="activeTab === 'logs'" />
  </NotebookCell>
</template>

<script setup lang="ts">
import type { NotebookCellNodeProps } from '@/components/notebooks/cell/cell.interface'
import { ref } from 'vue'
import { NOTEBOOK_ASSET_ICONS } from '@/components/notebooks/notebooks.const'
import NotebookCell from '@/components/notebooks/cell/NotebookCell.vue'
import NotebookCellTabs from '@/components/notebooks/cell/NotebookCellTabs.vue'
import NotebookPlot from '@/components/notebooks/cell/NotebookPlot.vue'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'

defineProps<NotebookCellNodeProps>()

const activeTab = ref('plot')
</script>

<style scoped></style>
