import { computed, ref } from 'vue'
import { defineStore } from 'pinia'
import { useIntervalFn } from '@vueuse/core'
import {
  Compare,
  Granularity,
  SeverityFilter,
  Window,
  type Dimensions,
} from '@/api/monitoring/interfaces'
import { AutoRefresh } from '@/types/filters'

export const useFiltersStore = defineStore('filters', () => {
  const selectedWindow = ref<Window>(Window.H24)
  const isCustomMode = ref(false)
  const customStart = ref<string | null>(null)
  const customEnd = ref<string | null>(null)
  const severity = ref<SeverityFilter>(SeverityFilter.ALL)
  const compare = ref<Compare>(Compare.OFF)
  const compareStart = ref<string | null>(null)
  const compareEnd = ref<string | null>(null)
  const granularity = ref<Granularity>(Granularity.AUTO)
  const feature = ref<string | null>(null)
  const autoRefresh = ref<AutoRefresh>(AutoRefresh.OFF)
  const refreshKey = ref(0)

  const isCustomRange = computed(() => customStart.value !== null && customEnd.value !== null)

  const activeWindow = computed(() => (isCustomMode.value ? null : selectedWindow.value))

  const isCompareActive = computed(() => compare.value !== Compare.OFF)

  const dimensions = computed<Dimensions>(() => ({
    window: isCustomRange.value ? null : selectedWindow.value,
    compare: compare.value,
    severity: severity.value,
    granularity: granularity.value,
    feature: feature.value,
    start: isCustomRange.value ? customStart.value : null,
    end: isCustomRange.value ? customEnd.value : null,
    compareStart: compareStart.value,
    compareEnd: compareEnd.value,
  }))

  const autoRefreshTimer = useIntervalFn(refresh, () => autoRefresh.value * 1000, {
    immediate: false,
  })

  function setWindow(value: Window) {
    selectedWindow.value = value
    isCustomMode.value = false
    customStart.value = null
    customEnd.value = null
  }

  function enableCustomMode() {
    isCustomMode.value = true
  }

  function cancelCustomMode() {
    if (!isCustomRange.value) isCustomMode.value = false
  }

  function setCustomRange(start: Date, end: Date) {
    customStart.value = start.toISOString()
    customEnd.value = end.toISOString()
  }

  function setSeverity(value: SeverityFilter) {
    severity.value = value
  }

  function setCompare(value: Compare) {
    compare.value = value
    compareStart.value = null
    compareEnd.value = null
  }

  function setCompareRange(start: Date, end: Date) {
    compare.value = Compare.CUSTOM
    compareStart.value = start.toISOString()
    compareEnd.value = end.toISOString()
  }

  function setGranularity(value: Granularity) {
    granularity.value = value
  }

  function setFeature(value: string | null) {
    feature.value = value
  }

  function setAutoRefresh(value: AutoRefresh) {
    autoRefresh.value = value
    if (value === AutoRefresh.OFF) autoRefreshTimer.pause()
    else autoRefreshTimer.resume()
  }

  function refresh() {
    refreshKey.value += 1
  }

  return {
    selectedWindow,
    isCustomMode,
    customStart,
    customEnd,
    severity,
    compare,
    compareStart,
    compareEnd,
    granularity,
    feature,
    autoRefresh,
    refreshKey,
    isCustomRange,
    activeWindow,
    isCompareActive,
    dimensions,
    setWindow,
    setCustomRange,
    enableCustomMode,
    cancelCustomMode,
    setSeverity,
    setCompare,
    setCompareRange,
    setGranularity,
    setFeature,
    setAutoRefresh,
    refresh,
  }
})
