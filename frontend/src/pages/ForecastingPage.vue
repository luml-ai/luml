<template>
  <forecasting-wrapper :steps="forecastingSteps" :task="Tasks.FORECASTING"></forecasting-wrapper>
</template>

<script setup lang="ts">
import ForecastingWrapper from '@/components/express-tasks/forecasting/ForecastingWrapper.vue'
import { Tasks } from '@/lib/data-processing/interfaces'
import { forecastingSteps } from '@/constants/constants'
</script>

<style scoped></style>
