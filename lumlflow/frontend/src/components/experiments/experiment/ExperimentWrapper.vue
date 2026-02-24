<template>
  <Card class="flex-1 overflow-hidden">
    <template #content>
      <ExperimentToolbar />
      <ExperimentTable :group-id="props.groupId" />
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
  groupId: string
}

const props = defineProps<Props>()
</script>

<style scoped></style>
