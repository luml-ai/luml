<template>
  <div class="empty-state">
    <span class="empty-title">{{ title }}</span>
    <span v-if="detail" class="empty-detail">{{ detail }}</span>
  </div>
</template>

<script setup lang="ts">
interface Props {
  title?: string
  detail?: string
}

withDefaults(defineProps<Props>(), {
  title: 'No data',
})
</script>

<style scoped>
.empty-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 16px;
  border: 1px solid var(--p-content-border-color);
  border-radius: var(--p-card-border-radius);
  background: var(--p-card-background);
  box-shadow: var(--p-card-shadow);
  text-align: center;
}

.empty-title {
  max-width: 100%;
  overflow: hidden;
  font-size: 16px;
  font-weight: 500;
  color: var(--p-text-color);
  text-overflow: ellipsis;
  white-space: nowrap;
}

.empty-detail {
  font-size: 12px;
  color: var(--p-text-muted-color);
}
</style>
