<template>
  <ul class="parameters__list">
    <li
      v-for="[key, value] of Object.entries(parameters)"
      :key="key"
      class="parameters__item parameter"
    >
      <div class="parameter__label">{{ key }}</div>
      <div class="parameter__value">
        {{ typeof value === 'object' && value.length ? value.join(', ') : value }}
      </div>
    </li>
  </ul>
</template>

<script setup lang="ts">
type Props = {
  parameters: Record<string, any>
}

defineProps<Props>()
</script>

<style scoped>
.parameters__list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.parameter {
  display: grid;
  grid-template-columns: 130px 1fr;
  gap: 24px;
  font-size: 14px;
}
.parameter__label {
  color: var(--p-text-muted-color);
  overflow: hidden;
  text-overflow: ellipsis;
}
</style>
