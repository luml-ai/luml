import { computed, shallowRef, watch } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import type { HeaderResponse, ModelKind, WorkerHealthResponse } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'

export const useHeaderStore = defineStore('header', () => {
  const filtersStore = useFiltersStore()

  const header = shallowRef<HeaderResponse | null>(null)
  const error = shallowRef<Error | null>(null)
  const workerHealth = shallowRef<WorkerHealthResponse | null>(null)

  const modelKind = computed<ModelKind>(() => header.value?.model_kind ?? 'unknown')

  const title = computed(() => header.value?.name ?? header.value?.model_name ?? '')

  async function loadWorkerHealth() {
    try {
      workerHealth.value = await filtersStore.trackRequest(api.monitoring.getWorkerHealth())
    } catch {
      return
    }
  }

  async function loadHeader() {
    void loadWorkerHealth()
    try {
      header.value = await filtersStore.trackRequest(api.monitoring.getHeader())
      error.value = null
    } catch (e) {
      error.value = e instanceof Error ? e : new Error(String(e))
    }
  }

  watch(() => filtersStore.refreshKey, loadHeader)

  return {
    header,
    error,
    workerHealth,
    modelKind,
    title,
    loadHeader,
  }
})
