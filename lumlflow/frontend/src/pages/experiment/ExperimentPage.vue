<template>
  <div>
    <ExperimentBreadcrumbs :experiment="experiment" />
    <h1 class="text-2xl font-medium pt-5 mb-7">{{ experiment.name }}</h1>
    <ExperimentWrapper />
  </div>
</template>

<script setup lang="ts">
import type { Group } from '@/store/groups/groups.interface'
import { MOCK_GROUPS } from '@/store/groups/groups.mock'
import { ref } from 'vue'
import ExperimentBreadcrumbs from '@/components/experiments/experiment/ExperimentBreadcrumbs.vue'
import ExperimentWrapper from '@/components/experiments/experiment/ExperimentWrapper.vue'

const experiment = ref<Group>(MOCK_GROUPS[0])
</script>

<style scoped></style>
