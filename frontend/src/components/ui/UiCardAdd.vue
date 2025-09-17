<template>
  <div class="card">
    <Button severity="secondary" rounded @click="$emit('add')">
      <template #icon>
        <Plus :size="14" />
      </template>
    </Button>
    <h3 class="title">{{ title }}</h3>
    <p class="text">{{ text }}</p>
  </div>
</template>

<script setup lang="ts">
import { Button } from 'primevue'
import { Plus } from 'lucide-vue-next'

type Props = {
  title: string
  text: string
}

type Emits = {
  add: []
}

defineProps<Props>()
defineEmits<Emits>()
</script>

<style scoped>
.card {
  padding: 16px 16px 20px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
  min-height: 149px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  align-items: center;
  gap: 8px;
  border-radius: 8px;
}

.title {
  font-size: 16px;
  font-weight: 500;
  display: flex;
  gap: 6px;
  align-items: center;
}

.text {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
