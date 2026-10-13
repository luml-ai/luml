<template>
  <RightFullHeightDialog v-model:visible="visible" :title="cell.slug">
    <div>
      <div v-for="output in outputs" :key="output.name" class="item">
        <div class="item-header">
          <div class="item-title mb-4">{{ output.label }}</div>
        </div>
        <div class="item-content">
          <NotebookOutput :slug="cell.slug" :name="output.name" />
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
import { computed } from 'vue'
import RightFullHeightDialog from '@/dialogs/RightFullHeightDialog.vue'
import { capitalize } from '@/helpers/string'
import NotebookOutput from '@/components/notebooks/cell/NotebookOutput.vue'
import NotebookCode from '@/components/notebooks/cell/NotebookCode.vue'
import NotebookLogs from '@/components/notebooks/cell/NotebookLogs.vue'

const props = defineProps<ExpandedCellProps>()

const visible = defineModel<boolean>('visible', { required: true })

const outputs = computed(() =>
  Object.keys(props.cell.kinds).map((name) => ({ name, label: capitalize(name) })),
)
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
