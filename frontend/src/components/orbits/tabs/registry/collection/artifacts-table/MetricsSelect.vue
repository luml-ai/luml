<template>
  <div class="wrapper">
    <label class="label" for="metrics">Metrics</label>
    <MultiSelect
      id="metrics"
      v-model="state"
      :options="props.metrics"
      placeholder="Select metrics"
      fluid
      class="select"
      size="small"
      filter
      :selectionLimit="100"
      :virtualScrollerOptions="{ itemSize: 35 }"
      :pt="multiSelectPt"
      @before-hide="onBeforeHide"
    />
  </div>
</template>

<script setup lang="ts">
import { MultiSelect, type MultiSelectPassThroughOptions } from 'primevue'
import { ref, watch } from 'vue'

const multiSelectPt: MultiSelectPassThroughOptions = {
  pcHeaderCheckbox: {
    root: {
      style: 'display: none !important;',
    },
  },
  pcFilter: {
    root: {
      class: 'p-inputtext-sm p-inputfield-sm',
    },
  },
}

type Props = {
  metrics: string[]
}

const props = defineProps<Props>()

const modelValue = defineModel<string[] | null>('modelValue')

const state = ref<string[] | null>(null)

function onBeforeHide() {
  modelValue.value = state.value ? [...state.value] : null
}

watch(modelValue, (value) => {
  state.value = value ? [...value] : null
})
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
