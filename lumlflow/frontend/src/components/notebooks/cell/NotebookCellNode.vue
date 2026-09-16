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
    <NotebookCellTabs v-model="activeTab" :tabs="tabs" class="mb-4" />
    <NotebookCode v-if="activeTab === CODE_TAB_ID" :slug="cell.slug" />
    <NotebookLogs v-else-if="activeTab === LOGS_TAB_ID" :slug="cell.slug" />
    <CellOutputTabContent v-else :content="content" />
  </NotebookCell>
</template>

<script setup lang="ts">
import type { NotebookCellNodeProps } from '@/components/notebooks/cell/cell.interface'
import { toRef } from 'vue'
import { NOTEBOOK_ASSET_ICONS } from '@/components/notebooks/notebooks.const'
import NotebookCell from '@/components/notebooks/cell/NotebookCell.vue'
import NotebookCellTabs from '@/components/notebooks/cell/NotebookCellTabs.vue'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'
import CellOutputTabContent from '@/components/notebooks/cell/preview/CellOutputTabContent.vue'
import { CODE_TAB_ID, LOGS_TAB_ID, useCellTabs } from '@/composables/useCellTabs'

const props = defineProps<NotebookCellNodeProps>()

const { tabs, activeTab, content } = useCellTabs(toRef(props, 'cell'))
</script>

<style scoped></style>
