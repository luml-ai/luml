<template>
  <div class="content">
    <GitBranch :size="35" color="var(--p-primary-color)" />
    <h3 class="label">Get started with Tracks</h3>
    <div class="text">
      <p>Track your best artifacts across versions and stages — from Staging to Production.</p>
      <p>Start by creating your first track.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { GitBranch } from 'lucide-vue-next'
</script>

<style scoped>
.content {
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  text-align: center;
  gap: 8px;
  min-height: 150px;
  border-radius: 8px;
  box-shadow: var(--card-shadow);
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
}

.label {
  font-weight: 500;
}

.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
