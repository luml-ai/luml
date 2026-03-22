<template>
  <div>
    <GroupsComparisonBreadcrumbs />
    <h1 class="text-2xl font-medium pt-5 mb-7">Groups Comparison</h1>
    <Skeleton v-if="loading" class="h-[calc(100vh-200px)]" height="calc(100vh-200px)"></Skeleton>
    <ExperimentWrapper
      v-else-if="groupsIds"
      :groups-ids="groupsIds"
      :dynamic-metrics="dynamicMetrics"
    />
    <div v-else>No groups selected</div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeMount, ref } from 'vue'
import { useRoute } from 'vue-router'
import { apiService } from '@/api/api.service'
import { useToast, Skeleton } from 'primevue'
import { errorToast } from '@/toasts'
import GroupsComparisonBreadcrumbs from '@/components/groups-comparison/GroupsComparisonBreadcrumbs.vue'
import ExperimentWrapper from '@/components/experiments/experiment/ExperimentWrapper.vue'

const route = useRoute()
const toast = useToast()

const dynamicMetrics = ref<string[]>([])
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
    const metrics = await apiService.getGroupsDynamicMetrics(groupsIds.value)
    dynamicMetrics.value = metrics
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
