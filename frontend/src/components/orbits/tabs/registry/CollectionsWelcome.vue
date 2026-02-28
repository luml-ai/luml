<template>
  <div class="content">
    <Folders :size="35" color="var(--p-primary-color)" />
    <h3 class="label">Welcome to the Registry</h3>
    <div class="text">
      <p>
        Organize your best model checkpoints into collections for easy access, versioning, and
        collaboration.
      </p>
      <p>Start by creating your first collection.</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Folders } from 'lucide-vue-next'
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
