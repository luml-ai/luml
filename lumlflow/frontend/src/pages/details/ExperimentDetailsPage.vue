<template>
  <template v-if="loading">Loading...</template>

  <div v-else-if="groupData && experimentStore.experiment">
    <DetailsBreadcrumbs
      :group-name="groupData.name"
      :group-id="groupId"
      :experiment-name="experimentStore.experiment.name"
      :experiment-id="experimentId"
    />
    <h1 class="text-2xl font-medium pt-2 mb-2">Test experiment</h1>
    <DetailsTabs class="mb-4" />
    <RouterView />
  </div>
  <div v-else>Experiment not found...</div>
</template>

<script setup lang="ts">
import type { Group } from '@/store/groups/groups.interface'
import { useRoute } from 'vue-router'
import { computed, onUnmounted, ref, watch } from 'vue'
import { apiService } from '@/api/api.service'
import { useExperimentStore } from '@/store/experiment'
import { useToast } from 'primevue'
import { errorToast } from '@/toasts'
import DetailsBreadcrumbs from '@/components/experiments/details/DetailsBreadcrumbs.vue'
import DetailsTabs from '@/components/experiments/details/DetailsTabs.vue'

const route = useRoute()
const toast = useToast()
const experimentStore = useExperimentStore()

const loading = ref(true)
const groupData = ref<Group | null>(null)

const groupId = computed(() => route.params.groupId as string)
const experimentId = computed(() => route.params.experimentId as string)

async function fetchData(groupId: string, experimentId: string) {
  try {
    loading.value = true
    const group = await apiService.getGroup(groupId)
    groupData.value = group
    await experimentStore.fetchExperiment(experimentId)
  } catch (error) {
    toast.add(errorToast(error))
    console.error(error)
  } finally {
    loading.value = false
  }
}

watch([groupId, experimentId], ([groupId, experimentId]) => fetchData(groupId, experimentId), {
  immediate: true,
})

onUnmounted(() => {
  experimentStore.resetExperiment()
})
</script>

<style scoped></style>
