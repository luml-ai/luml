<template>
  <Card class="flex-1 overflow-hidden">
    <template #content>
      <ExperimentToolbar />
      <ExperimentTable />
    </template>
  </Card>
  <ExperimentEdit />
</template>

<script setup lang="ts">
import { Card } from 'primevue'
import ExperimentToolbar from './ExperimentToolbar.vue'
import ExperimentTable from './ExperimentTable.vue'
import ExperimentEdit from './ExperimentEdit.vue'
</script>

<style scoped></style>
