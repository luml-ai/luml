<template>
  <div class="dataset-wrapper">
    <div class="dataset-header">
      <Database :size="20" color="var(--p-primary-color)" />
      <h2 class="title">Dataset</h2>
    </div>
    <div class="dataset-body">
      <slot></slot>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Database } from 'lucide-vue-next'
</script>

<style scoped>
.dataset-wrapper {
  padding: 12px;
  border: 1px solid var(--p-content-border-color);
  border-radius: 8px;
  background-color: var(--p-card-background);
  box-shadow: var(--card-shadow);
  height: calc(100vh - 310px);
  overflow-y: auto;
}

.dataset-header {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 0;
  margin-bottom: 12px;
}

.title {
  padding-right: 10px;
  font-size: 20px;
  font-weight: 400;
}
</style>
