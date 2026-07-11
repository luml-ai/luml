<template>
  <div>
    <GroupsComparisonBreadcrumbs />
    <h1 class="text-2xl font-medium pt-5 mb-7">Groups Comparison</h1>
    <Skeleton v-if="loading" class="h-[calc(100vh-200px)]" height="calc(100vh-200px)"></Skeleton>
    <ExperimentWrapper
      v-else-if="groupsIds"
      :groups-ids="groupsIds"
      :dynamic-metrics="experimentsStore.dynamicMetrics"
    />
    <div v-else>No groups selected</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { useToast, Skeleton } from 'primevue'
import { errorToast } from '@/toasts'
import { useExperimentsStore } from '@/store/experiments'
import GroupsComparisonBreadcrumbs from '@/components/groups-comparison/GroupsComparisonBreadcrumbs.vue'
import ExperimentWrapper from '@/components/experiments/experiment/ExperimentWrapper.vue'

const route = useRoute()
const toast = useToast()
const experimentsStore = useExperimentsStore()

const loading = ref(true)

const groupsIds = computed(() => {
  const ids = route.query.groupsIds
  if (!ids || typeof ids === 'string') {
    toast.add(errorToast('Groups IDs are required'))
    return []
  }
  return ids.map(String)
})

onBeforeMount(async () => {
  try {
    await experimentsStore.fetchDynamicMetrics(groupsIds.value)
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
