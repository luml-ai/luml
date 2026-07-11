<template>
  <tabular-wrapper :steps="tabularSteps" :task="Tasks.TABULAR_REGRESSION"></tabular-wrapper>
</template>

<script setup lang="ts">
import TabularWrapper from '@/components/express-tasks/tabular/TabularWrapper.vue'
import { Tasks } from '@/lib/data-processing/interfaces'
import { tabularSteps } from '@/constants/constants'
</script>

<style scoped></style>
