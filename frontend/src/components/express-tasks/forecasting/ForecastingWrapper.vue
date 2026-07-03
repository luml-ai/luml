<template>
  <div class="forecasting-wrapper">
    <ol class="steps">
      <li v-for="step in steps" :key="step.id" class="step">
        {{ step.text }}
      </li>
    </ol>
  </div>
</template>

<script setup lang="ts">
import type { Tasks } from '@/lib/data-processing/interfaces'

type Step = {
  id: number
  text: string
}

defineProps<{
  steps: Step[]
  task: Tasks.FORECASTING
}>()
</script>

<style scoped>
.forecasting-wrapper {
  padding-top: 32px;
}
</style>
