<template>
  <RightFullHeightDialog v-model:visible="visible" :title="cell.slug">
    <div>
      <div class="item">
        <div class="item-header">
          <div class="item-title mb-4">Plot</div>
        </div>
        <div class="item-content">
          <NotebookPlot />
        </div>
      </div>
      <div class="item">
        <div class="item-header">
          <div class="item-title -mb-9">Code</div>
        </div>
        <div class="item-content">
          <NotebookCode :slug="cell.slug" />
        </div>
      </div>
      <div class="item">
        <div class="item-header">
          <div class="item-title mb-4">Logs</div>
        </div>
        <div class="item-content">
          <NotebookLogs :slug="cell.slug" />
        </div>
      </div>
    </div>
  </RightFullHeightDialog>
</template>

<script setup lang="ts">
import type { ExpandedCellProps } from '@/components/notebooks/cell/cell.interface'
import RightFullHeightDialog from '@/dialogs/RightFullHeightDialog.vue'
import NotebookPlot from '@/components/notebooks/cell/NotebookPlot.vue'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'

defineProps<ExpandedCellProps>()

const visible = defineModel<boolean>('visible', { required: true })
</script>

<style scoped>
@reference "@/assets/css/index.css";

.item {
}
.item-header {
  @apply flex items-center justify-between;
}
.item-title {
  @apply text-sm relative z-10;
}
.item-content {
  @apply pb-4 not-last:border-b border-surface not-last:mb-4;
}
</style>
