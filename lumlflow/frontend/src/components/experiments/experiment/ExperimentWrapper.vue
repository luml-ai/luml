<template>
  <Card class="flex-1 overflow-hidden">
    <template #content>
      <ExperimentToolbar />
      <ExperimentTable :groups-ids="props.groupsIds" :dynamic-metrics="props.dynamicMetrics" />
    </template>
  </Card>
  <ExperimentEdit />
</template>

<script setup lang="ts">
import { Card } from 'primevue'
import ExperimentToolbar from './ExperimentToolbar.vue'
import ExperimentTable from './ExperimentTable.vue'
import ExperimentEdit from './ExperimentEdit.vue'

interface Props {
  groupsIds: string[]
  dynamicMetrics: string[]
}

const props = defineProps<Props>()
</script>

<style scoped></style>
