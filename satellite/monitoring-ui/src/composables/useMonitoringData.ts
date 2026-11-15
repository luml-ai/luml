import { ref, shallowRef, watch } from 'vue'
import type { Dimensions } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'

export function useMonitoringData<T>(fetcher: (dims: Dimensions) => Promise<T>) {
  const filtersStore = useFiltersStore()

  const data = shallowRef<T | null>(null)
  const error = shallowRef<Error | null>(null)
  const loading = ref(false)
  let requestId = 0

  async function load() {
    const id = ++requestId
    loading.value = true
    try {
      const result = await fetcher(filtersStore.dimensions)
      if (id !== requestId) return
      data.value = result
      error.value = null
    } catch (e) {
      if (id !== requestId) return
      error.value = e instanceof Error ? e : new Error(String(e))
    } finally {
      if (id === requestId) loading.value = false
    }
  }

  watch(() => [filtersStore.dimensions, filtersStore.refreshKey], load, { immediate: true })

  return { data, error, loading, reload: load }
}
