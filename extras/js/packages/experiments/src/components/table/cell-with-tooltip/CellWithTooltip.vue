<template>
  <div>
    <div v-if="isEmpty">-</div>
    <div v-else v-tooltip.top="valueText" class="cell">
      {{ valueText }}
    </div>
  </div>
</template>

<script setup lang="ts">
import { valueToString } from '@/helpers/texts'
import { computed } from 'vue'
import { isLargeText, previewText } from '../../ui/largeValue'

interface Props {
  value: any
}

const props = defineProps<Props>()

// The cell shows one cut line, so a large value only needs its start. Compact JSON is
// a much cheaper size check than YAML, so large objects are cut from it and never
// converted to YAML.
const valueText = computed(() => {
  if (typeof props.value === 'object' && props.value !== null) {
    const json = JSON.stringify(props.value)
    if (isLargeText(json)) return `${previewText(json)}…`
  }
  const text = valueToString(props.value)
  return text && isLargeText(text) ? `${previewText(text)}…` : text
})

const isEmpty = computed(
  () => props.value === null || props.value === undefined || props.value === '',
)
</script>

<style scoped>
.cell {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}
</style>
