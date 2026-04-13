<template>
  <div v-if="!data">-</div>
  <div v-else class="feedback-column">
    <UiFeedbackResult
      v-if="data?.positiveCount"
      :positive="true"
      :count="data?.positiveCount"
    ></UiFeedbackResult>
    <UiFeedbackResult
      v-if="data?.negativeCount"
      :positive="false"
      :count="data?.negativeCount"
    ></UiFeedbackResult>
  </div>
</template>

<script setup lang="ts">
import type { FeedbackColumnProps } from './interface'
import UiFeedbackResult from '@experiments/components/ui/UiFeedbackResult.vue'

defineProps<FeedbackColumnProps>()
</script>

<style scoped>
.feedback-column {
  display: flex;
  align-items: center;
  gap: 7px;
}
</style>
