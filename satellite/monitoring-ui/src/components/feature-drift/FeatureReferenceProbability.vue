<template>
  <div class="probability">
    <div class="head">
      <MEllipsis class="label" :text="label" />
      <span class="value">{{ value }}</span>
    </div>
    <div class="track">
      <div class="bar" :style="{ width }" />
    </div>
  </div>
</template>

<script setup lang="ts">
import MEllipsis from '@/components/MEllipsis.vue'

interface Props {
  label: string
  value: string
  width: string
}

defineProps<Props>()
</script>

<style scoped>
.probability {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.head {
  display: flex;
  justify-content: space-between;
  gap: 16px;
  font-size: 14px;
  font-weight: 500;
  color: var(--p-text-color);
}

.label {
  min-width: 0;
}

.value {
  flex-shrink: 0;
}

.track {
  height: 6px;
  overflow: hidden;
  border-radius: 6px;
  background: var(--p-tag-secondary-background);
}

.bar {
  height: 100%;
  border-radius: 6px;
  background: var(--p-primary-color);
}
</style>
