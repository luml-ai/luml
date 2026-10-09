<template>
  <div class="monitoring-state" :data-testid="testid">
    <div class="monitoring-state__icon">
      <slot name="icon" />
    </div>
    <h2 class="monitoring-state__title">{{ title }}</h2>
    <p class="monitoring-state__description">{{ description }}</p>
    <div v-if="$slots.action" class="monitoring-state__action">
      <slot name="action" />
    </div>
  </div>
</template>

<script setup lang="ts">
type Props = {
  title: string
  description: string
  testid?: string
}

defineProps<Props>()
</script>

<style scoped>
.monitoring-state {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 12px;
  text-align: center;
  min-height: 320px;
  padding: 40px 20px;
}

.monitoring-state__icon {
  color: var(--p-text-muted-color);
}

.monitoring-state__title {
  font-size: 18px;
  font-weight: 500;
}

.monitoring-state__description {
  max-width: 420px;
  color: var(--p-text-muted-color);
}

.monitoring-state__action {
  margin-top: 8px;
}
</style>
