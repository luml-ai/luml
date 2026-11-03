<template>
  <div class="info-block">
    <Info :size="16" class="icon" />
    <div>
      <div class="info-title">{{ title }}</div>
      <div v-if="text" class="info-text">{{ text }}</div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { Info } from 'lucide-vue-next'

interface UiInfoBlockProps {
  title: string
  text?: string
}

defineProps<UiInfoBlockProps>()
</script>

<style scoped>
.info-block {
  padding: var(--p-toast-content-padding);
  gap: var(--p-toast-content-gap);
  border-radius: var(--p-toast-border-radius);
  background-color: var(--p-toast-info-background);
  border-color: var(--p-toast-info-border-color);
  border-style: solid;
  border-width: var(--p-toast-border-width);
  color: var(--p-toast-info-color);
  display: flex;
}

.icon {
  flex-shrink: 0;
}

.info-title {
  font-size: var(--p-toast-summary-font-size);
  font-weight: var(--p-toast-summary-font-weight);
}

.info-text {
  font-size: var(--p-toast-detail-font-size);
  color: var(--p-toast-info-detail-color);
  padding-top: 8px;
}
</style>
