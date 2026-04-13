<template>
  <div v-if="!data">-</div>
  <div v-else class="expectation-column">
    <UiFeedbackResult
      v-if="data?.positive"
      :positive="true"
      :count="data?.positive"
    ></UiFeedbackResult>
    <UiFeedbackResult
      v-if="data?.negative"
      :positive="false"
      :count="data?.negative"
    ></UiFeedbackResult>
    <div v-tooltip.top="String(data?.value)" class="first-value">{{ data?.value }}</div>
    <Tag v-if="tagText" :value="tagText" class="tag" />
  </div>
</template>

<script setup lang="ts">
import type { ExpectationColumnProps } from './interface'
import { computed } from 'vue'
import { Tag } from 'primevue'
import UiFeedbackResult from '@experiments/components/ui/UiFeedbackResult.vue'

const props = defineProps<ExpectationColumnProps>()

const tagText = computed(() => {
  if (!props.data) return null
  const { total = 0, positive = 0, negative = 0 } = props.data
  const count = total - positive - negative - 1
  if (count <= 0) return null
  return `+${count}`
})
</script>

<style scoped>
.expectation-column {
  display: flex;
  align-items: center;
  gap: 7px;
}

.first-value {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  flex: 1 1 80px;
}

.tag {
  border-radius: 4px;
  padding: 2px 6px;
}
</style>
