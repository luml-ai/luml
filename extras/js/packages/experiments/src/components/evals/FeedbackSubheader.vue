<template>
  <div class="feedback-subheader">
    <UiFeedbackResult :positive="true" :percentage="positivePercentage"></UiFeedbackResult>
    <UiFeedbackResult :positive="false" :percentage="negativePercentage"></UiFeedbackResult>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import UiFeedbackResult from '../ui/UiFeedbackResult.vue'
import type { AnnotationSummary } from '@/components/annotations/annotations.interface'

interface Props {
  feedback: AnnotationSummary['feedback']
  annotationName: string
}

const props = defineProps<Props>()

const annotationData = computed(() => {
  return props.feedback.find(
    (item) => item.name === props.annotationName.replace(' (feedback)', ''),
  )
})

const positivePercentage = computed(() => {
  return ((annotationData.value?.counts['true'] ?? 0) / (annotationData.value?.total ?? 1)) * 100
})

const negativePercentage = computed(() => {
  return ((annotationData.value?.counts['false'] ?? 0) / (annotationData.value?.total ?? 1)) * 100
})
</script>

<style scoped>
.feedback-subheader {
  display: flex;
  gap: 8px;
  flex-direction: column;
  gap: 16px;
}
</style>
