<template>
  <div class="card coming-soon" data-testid="coming-soon">
    <Construction :size="24" class="icon" />
    <p class="title">{{ title }}</p>
    <p class="detail">This view is coming soon.</p>
  </div>
</template>

<script setup lang="ts">
import { Construction } from 'lucide-vue-next'

defineProps<{ title: string }>()
</script>

<style scoped>
.coming-soon {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  gap: var(--luml-space-2);
  padding: var(--luml-space-10) var(--luml-space-5);
  color: var(--luml-fg-muted);
}
.icon {
  color: var(--luml-fg-faint);
}
.title {
  margin: var(--luml-space-2) 0 0;
  font-weight: 600;
  color: var(--luml-fg-strong);
}
.detail {
  margin: 0;
  font-size: var(--luml-caption-size);
}
</style>
