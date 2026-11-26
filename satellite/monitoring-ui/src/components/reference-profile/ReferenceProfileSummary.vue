<template>
  <dl class="summary">
    <div v-for="item in items" :key="item.label" class="item">
      <dt class="label">{{ item.label }}:</dt>
      <dd class="value">
        <Tag :value="item.value" severity="secondary" />
      </dd>
    </div>
  </dl>
</template>

<script setup lang="ts">
import Tag from 'primevue/tag'
import type { ReferenceProfileSummaryItem } from '@/types/reference-profile'

interface Props {
  items: ReferenceProfileSummaryItem[]
}

defineProps<Props>()
</script>

<style scoped>
.summary {
  display: flex;
  flex-wrap: wrap;
  justify-content: space-between;
  gap: 16px 24px;
  margin: 0;
}

.item {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
}

.label {
  font-size: 14px;
  line-height: 21px;
  color: var(--p-text-color);
}

.value {
  margin: 0;
}
</style>
