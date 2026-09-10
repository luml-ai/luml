<template>
  <div class="card">
    <NotebookCellHeader :title="title" :icon="icon" :cost-seconds="costSeconds" :cell="cell" />
    <div class="py-4">
      <slot> </slot>
    </div>
    <NotebookCellFooter :state="state" :causes="causes" :reused="reused" :cell="cell" />
  </div>
</template>

<script setup lang="ts">
import type { NotebookCellProps } from '@/components/notebooks/cell/cell.interface'
import NotebookCellHeader from '@/components/notebooks/cell/NotebookCellHeader.vue'
import NotebookCellFooter from '@/components/notebooks/cell/NotebookCellFooter.vue'

defineProps<NotebookCellProps>()
</script>

<style scoped>
@reference "@/assets/css/index.css";

.card {
  @apply bg-(--p-card-background) border border-surface rounded-lg overflow-hidden p-5 shadow-(--p-card-shadow);
}
</style>
