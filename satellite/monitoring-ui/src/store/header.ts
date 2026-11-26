import { computed, shallowRef, watch } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import {
  ProfileStatus,
  SectionState,
  type HeaderResponse,
  type ModelKind,
  type WorkerHealthResponse,
} from '@/api/monitoring/interfaces'
import { useFiltersStore } from '@/store/filters'

export const useHeaderStore = defineStore('header', () => {
  const filtersStore = useFiltersStore()

  const header = shallowRef<HeaderResponse | null>(null)
  const error = shallowRef<Error | null>(null)
  const isUnavailable = shallowRef(false)
  const workerHealth = shallowRef<WorkerHealthResponse | null>(null)
  const sectionProfileStatus = shallowRef<ProfileStatus | null>(null)
  let headerRequestId = 0
  let workerRequestId = 0

  const modelKind = computed<ModelKind>(() => header.value?.model_kind ?? 'unknown')

  const title = computed(() => header.value?.name ?? header.value?.model_name ?? '')

  const status = computed(() => header.value?.status ?? null)

  const isContextMissing = computed(() => !header.value && (!!error.value || isUnavailable.value))

  const isPlaceholderProfile = computed(
    () =>
      header.value?.profile_status === ProfileStatus.PLACEHOLDER ||
      sectionProfileStatus.value === ProfileStatus.PLACEHOLDER,
  )

  function reportProfileStatus(value: ProfileStatus | null | undefined) {
    if (value) sectionProfileStatus.value = value
  }

  async function loadWorkerHealth() {
    const id = ++workerRequestId
    try {
      const result = await filtersStore.trackRequest(api.monitoring.getWorkerHealth())
      if (id === workerRequestId) workerHealth.value = result
    } catch {
      if (id === workerRequestId) workerHealth.value = null
    }
  }

  async function loadHeader() {
    void loadWorkerHealth()
    const id = ++headerRequestId
    try {
      const result = await filtersStore.trackRequest(api.monitoring.getHeader())
      if (id !== headerRequestId) return
      error.value = null
      isUnavailable.value = result.state === SectionState.UNAVAILABLE
      if (!isUnavailable.value) header.value = result
    } catch (e) {
      if (id !== headerRequestId) return
      error.value = e instanceof Error ? e : new Error(String(e))
    }
  }

  watch(() => filtersStore.refreshKey, loadHeader)

  return {
    header,
    error,
    isUnavailable,
    workerHealth,
    modelKind,
    title,
    status,
    isContextMissing,
    isPlaceholderProfile,
    reportProfileStatus,
    loadHeader,
  }
})
