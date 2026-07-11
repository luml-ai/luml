<template>
  <div class="metric">
    <h3 class="metric-title">{{ title }}</h3>
    <div class="results">
      <div
        class="result"
        v-for="(item, index) in items"
        :key="index"
        :class="{ primary: index === 0 }"
      >
        <h4 class="label">{{ index === 0 ? 'Eval' : 'Training' }}</h4>
        <div class="value">{{ item.value }}</div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
type Props = {
  title: string
  items: {
    value: string
  }[]
}

defineProps<Props>()
</script>

<style scoped>
.metric {
  padding: 12px;
  border-radius: 8px;
  border: 1px solid var(--p-content-border-color);
  background-color: var(--p-content-background);
  box-shadow: var(--card-shadow);
  display: flex;
  flex-direction: column;
}
.metric-title {
  margin-bottom: 16px;
  flex: 1 1 auto;
}
@media (max-width: 991.98px) {
  .metric-title {
    font-size: 1rem;
  }
}
.results {
  display: flex;
  gap: 52px;
}
.result {
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.label {
  font-size: 14px;
  color: var(--p-text-muted-color);
}

.value {
  line-height: 1.5;
}

.primary {
  color: var(--p-primary-color);
}

.primary .label {
  color: var(--p-primary-color);
}

.primary .value {
  font-size: 20px;
  font-weight: 600;
  line-height: 1;
}
</style>
