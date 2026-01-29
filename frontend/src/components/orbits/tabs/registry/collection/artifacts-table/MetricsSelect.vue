<template>
  <div class="wrapper">
    <label class="label" for="metrics">Metrics</label>
    <MultiSelect
      id="metrics"
      v-model="modelValue"
      :options="props.metrics"
      placeholder="Select metrics"
      fluid
      class="select"
      size="small"
      :virtualScrollerOptions="{ itemSize: 35 }"
    />
  </div>
</template>

<script setup lang="ts">
import { MultiSelect } from 'primevue'

type Props = {
  metrics: string[]
}

const props = defineProps<Props>()

const modelValue = defineModel<string[] | null>('modelValue')
</script>

<style scoped>
.wrapper {
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.label {
  font-size: 14px;
  text-align: right;
  color: var(--p-text-muted-color);
}

.select {
  width: 200px;
}
</style>
