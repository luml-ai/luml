<template>
  <div class="lanes-list">
    <NotebooksLanesListItem v-for="lane in flowStore.laneTree" :key="lane.id" :lane="lane" />
  </div>
</template>

<script setup lang="ts">
import { onMounted } from 'vue'
import { useFlowStore } from '@/store/flow'
import NotebooksLanesListItem from './NotebooksLanesListItem.vue'

const flowStore = useFlowStore()

onMounted(() => {
  flowStore.fetchBranches()
})
</script>

<style scoped>
@reference "@/assets/css/index.css";

.lanes-list {
  @apply flex flex-col px-4 pb-2 max-h-72.5 overflow-y-auto;
}
</style>
