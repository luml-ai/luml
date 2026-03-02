<template>
  <Skeleton v-if="loading" class="h-[calc(100vh-250px)]" height="calc(100vh-250px)"></Skeleton>
  <div v-else-if="!tracesIds?.length">No traces found</div>
  <div v-else>
    <Button severity="secondary" fluid @click="showTraces">
      <ListTree :size="16" />
      Traces
    </Button>
    <TracesInfoDialog
      :visible="!!tracesData"
      :data="tracesData || []"
      @update:visible="onTracesInfoVisibleUpdate"
      @select="evalsStore.setSelectedTrace"
    ></TracesInfoDialog>
  </div>
</template>

<script setup lang="ts">
import type { Trace } from '@/store/experiments/experiments.interface'
import type { GetExperimentTracesParams } from '@/api/api.interface'
import type { BaseTraceInfo } from '@luml/experiments'
import { useRoute } from 'vue-router'
import { onBeforeMount, ref } from 'vue'
import { apiService } from '@/api/api.service'
import { usePagination } from '@/hooks/usePagination'
import { useToast, Button, Skeleton } from 'primevue'
import { errorToast } from '@/toasts'
import { useEvalsStore, TracesInfoDialog } from '@luml/experiments'
import { ListTree } from 'lucide-vue-next'

const route = useRoute()
const toast = useToast()
// const { data, getInitialPage, isLoading } = usePagination<Trace, GetExperimentTracesParams>(
//   apiService.getExperimentTraces,
//   {
//     experiment_id: String(route.params.experimentId),
//   },
// )
const evalsStore = useEvalsStore()

const loading = ref(true)
const tracesIds = ref<string[] | null>(null)
const tracesData = ref<BaseTraceInfo[] | null>(null)

async function showTraces() {
  try {
    tracesData.value = await getTracesData()
  } catch {
    toast.add(errorToast('Failed to load traces'))
  }
}

// async function getTracesData() {
//   if (!tracesIds.value) return []
//   const promises = tracesIds.value.map(async (traceId) => {
//     return evalsStore.getTraceSpansTree(String(route.params.experimentId), traceId)
//   })
//   return Promise.all(promises)
// }
async function getTracesData() {
  if (!tracesIds.value) return []

  const experimentId = String(route.params.experimentId)
  const ids = [...tracesIds.value]
  const results: any[] = []

  const concurrency = 10
  let index = 0

  async function worker() {
    while (index < ids.length) {
      const currentIndex = index++
      const traceId = ids[currentIndex]

      try {
        const res = await evalsStore.getTraceSpansTree(experimentId, traceId)
        results.push(res)
      } catch (e) {
        continue
      }
    }
  }

  await Promise.all(Array.from({ length: concurrency }, worker))

  return results
}

function onTracesInfoVisibleUpdate(value: boolean | undefined) {
  if (!value) {
    tracesData.value = null
  }
}

onBeforeMount(async () => {
  try {
    tracesIds.value = await evalsStore.getUniqueTraceIds(String(route.params.experimentId))
  } catch (error) {
    toast.add(errorToast(error))
  } finally {
    loading.value = false
  }
})
</script>

<style scoped></style>
