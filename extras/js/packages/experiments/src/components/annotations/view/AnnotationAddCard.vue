<template>
  <div class="card">
    <Button rounded severity="secondary" @click="$emit('add')">
      <template #icon>
        <Plus :size="14" />
      </template>
    </Button>
    <h3 class="title">Add annotation</h3>
    <p class="text">Start by creating an Annotation to organize your model score</p>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'

interface Emits {
  (event: 'add'): void
}

defineEmits<Emits>()
</script>

<style scoped>
.card {
  padding: 16px 16px 20px;
  max-width: 284px;
  min-height: 149px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
  text-align: center;
}
.title {
  font-weight: 500;
}
.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
