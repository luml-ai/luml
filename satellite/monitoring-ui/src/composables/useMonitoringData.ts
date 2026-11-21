import { computed, ref, shallowRef, watch } from 'vue'
import type { Dimensions, ProfileStatus } from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'
import { useHeaderStore } from '@/store/header'

interface MonitoringDataOptions {
  autoRefresh?: boolean
}

export function useMonitoringData<T>(
  fetcher: (dims: Dimensions) => Promise<T>,
  params?: () => unknown,
  options: MonitoringDataOptions = {},
) {
  const filtersStore = useFiltersStore()
  const headerStore = useHeaderStore()

  const data = shallowRef<T | null>(null)
  const error = shallowRef<Error | null>(null)
  const loading = ref(false)
  let requestId = 0
  let loadedFiltersKey: string | null = null

  const filtersKey = computed(() => JSON.stringify({ ...filtersStore.dimensions, feature: null }))

  const refreshKey = computed(() =>
    options.autoRefresh === false ? filtersStore.manualRefreshKey : filtersStore.refreshKey,
  )

  async function load() {
    const id = ++requestId
    const key = filtersKey.value
    if (loadedFiltersKey !== null && loadedFiltersKey !== key) {
      data.value = null
      loadedFiltersKey = null
    }
    loading.value = true
    try {
      const result = await filtersStore.trackRequest(fetcher(filtersStore.dimensions))
      if (id !== requestId) return
      data.value = result
      error.value = null
      loadedFiltersKey = key
      headerStore.reportProfileStatus(
        (result as { profile_status?: ProfileStatus } | null)?.profile_status,
      )
    } catch (e) {
      if (id !== requestId) return
      error.value = e instanceof Error ? e : new Error(String(e))
    } finally {
      if (id === requestId) loading.value = false
    }
  }

  watch(() => [filtersStore.dimensions, refreshKey.value, params?.()], load, {
    immediate: true,
  })

  return { data, error, loading, reload: load }
}
