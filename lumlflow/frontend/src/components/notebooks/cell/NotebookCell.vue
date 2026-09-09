<template>
  <div class="card">
    <NotebookCellHeader />
    <div class="py-4">
      <slot> Basic </slot>
    </div>
    <NotebookCellFooter />
  </div>
</template>

<script setup lang="ts">
import NotebookCellHeader from '@/components/notebooks/cell/NotebookCellHeader.vue'
import NotebookCellFooter from '@/components/notebooks/cell/NotebookCellFooter.vue'
</script>

<style scoped>
@reference "@/assets/css/index.css";

.card {
  @apply bg-(--p-card-background) border border-surface rounded-lg overflow-hidden p-5 shadow-(--p-card-shadow);
}
</style>
