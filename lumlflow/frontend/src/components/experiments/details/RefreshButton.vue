<template>
  <Button
    v-if="showRefreshButton"
    variant="outlined"
    severity="secondary"
    class="w-9 h-10"
    :loading="loading"
    @click="refresh"
  >
    <template #icon>
      <RotateCcw :size="14" color="var(--p-button-outlined-plain-color)" />
    </template>
  </Button>
</template>

<script setup lang="ts">
import { Button, useToast } from 'primevue'
import { RotateCcw } from 'lucide-vue-next'
import { useRoute } from 'vue-router'
import { computed, ref } from 'vue'
import { errorToast } from '@/toasts'
import { useExperimentStore } from '@/store/experiment'
import { useDynamicMetricsStore, useTraceStore, useEvalsStore } from '@luml/experiments'
import { ROUTE_NAMES } from '@/router/router.const'

const route = useRoute()
const toast = useToast()
const experimentStore = useExperimentStore()
const dynamicMetricsStore = useDynamicMetricsStore()
const tracesStore = useTraceStore()
const evalsStore = useEvalsStore()

const loading = ref(false)

const experimentId = computed(() => route.params.experimentId as string)

const showRefreshButton = computed(() => {
  return experimentStore.experiment?.status === 'active'
})

const refresh = async () => {
  try {
    loading.value = true
    await refreshExperimentData()
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
}

async function refreshExperimentData() {
  await experimentStore.fetchExperiment(experimentId.value)
  if (route.name === ROUTE_NAMES.EXPERIMENT_METRICS) {
    await dynamicMetricsStore.refresh()
  }
  if (route.name === ROUTE_NAMES.EXPERIMENT_TRACES) {
    await tracesStore.refresh()
  }
  if (route.name === ROUTE_NAMES.EXPERIMENT_EVALS) {
    await evalsStore.refresh()
  }
}
</script>

<style scoped></style>
