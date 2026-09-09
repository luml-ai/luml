<template>
  <RightFullHeightDialog v-model:visible="visible" :title="cell.slug">
    <div>
      <div class="item">
        <div class="item-header">
          <div class="item-title">Plot</div>
        </div>
        <div class="item-content">
          <NotebookPlot />
        </div>
      </div>
      <div class="item">
        <div class="item-header">
          <div class="item-title">Code</div>
          <Button severity="secondary" variant="outlined" class="w-10 h-10 p-0">
            <template #icon>
              <Pencil :size="14" />
            </template>
          </Button>
        </div>
        <div class="item-content">
          <NotebookCode />
        </div>
      </div>
      <div class="item">
        <div class="item-header">
          <div class="item-title">Logs</div>
        </div>
        <div class="item-content">
          <NotebookLogs />
        </div>
      </div>
    </div>
  </RightFullHeightDialog>
</template>

<script setup lang="ts">
import type { ExpandedCellProps } from '@/components/notebooks/cell/cell.interface'
import { Button } from 'primevue'
import { Pencil } from 'lucide-vue-next'
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
  @apply text-sm;
}
.item-content {
  @apply pb-4 not-last:border-b border-surface not-last:mb-4;
}
</style>
