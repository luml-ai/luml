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
import { onBeforeMount, onBeforeUnmount } from 'vue'
import { useExperimentsStore } from '@/store/experiments'
import { Card } from 'primevue'
import ExperimentToolbar from './ExperimentToolbar.vue'
import ExperimentTable from './ExperimentTable.vue'
import ExperimentEdit from './ExperimentEdit.vue'

interface Props {
  groupsIds: string[]
  dynamicMetrics: string[]
}

const props = defineProps<Props>()

const experimentsStore = useExperimentsStore()

onBeforeMount(async () => {
  await experimentsStore.fetchDynamicMetrics(props.groupsIds)
  await experimentsStore.fetchStaticParams(props.groupsIds)
})

onBeforeUnmount(() => {
  experimentsStore.resetDynamicMetrics()
  experimentsStore.resetStaticParams()
})
</script>

<style scoped></style>
