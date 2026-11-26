import { computed, ref, watch } from 'vue'
import { defineStore } from 'pinia'
import { api } from '@/api'
import { Compare, Granularity, SeverityFilter, Window } from '@/api/monitoring/interfaces'
import { AUTO_REFRESH_OPTIONS } from '@/constants/filters'
import type { AutoRefresh } from '@/types/filters'
import { TabKey } from '@/types/tabs'
import { useFiltersStore } from '@/store/filters'
import { useTabsStore } from '@/store/tabs'

const SETTINGS_VERSION = 1

interface StoredSettings {
  v: number
  window: Window
  start: string | null
  end: string | null
  compare: Compare
  compareStart: string | null
  compareEnd: string | null
  severity: SeverityFilter
  granularity: Granularity
  autoRefresh: AutoRefresh
  tab: TabKey
}

const oneOf = <T>(value: unknown, allowed: readonly T[]): T | null =>
  allowed.includes(value as T) ? (value as T) : null

const toDate = (value: unknown): Date | null => {
  if (typeof value !== 'string') return null
  const date = new Date(value)
  return Number.isNaN(date.getTime()) ? null : date
}

const readStorage = (key: string): Record<string, unknown> | null => {
  try {
    const raw = localStorage.getItem(key)
    if (!raw) return null
    const parsed: unknown = JSON.parse(raw)
    return typeof parsed === 'object' && parsed !== null
      ? (parsed as Record<string, unknown>)
      : null
  } catch {
    return null
  }
}

const writeStorage = (key: string, value: StoredSettings) => {
  try {
    localStorage.setItem(key, JSON.stringify(value))
  } catch {
    return
  }
}

export const useSettingsStore = defineStore('settings', () => {
  const filtersStore = useFiltersStore()
  const tabsStore = useTabsStore()

  const isReady = ref(false)
  const storageKey = ref<string | null>(null)

  const snapshot = computed<StoredSettings>(() => ({
    v: SETTINGS_VERSION,
    window: filtersStore.selectedWindow,
    start: filtersStore.isCustomRange ? filtersStore.customStart : null,
    end: filtersStore.isCustomRange ? filtersStore.customEnd : null,
    compare: filtersStore.compare,
    compareStart: filtersStore.compareStart,
    compareEnd: filtersStore.compareEnd,
    severity: filtersStore.severity,
    granularity: filtersStore.granularity,
    autoRefresh: filtersStore.autoRefresh,
    tab: tabsStore.selectedTab,
  }))

  function apply(blob: Record<string, unknown>) {
    if (blob.v !== SETTINGS_VERSION) return
    const selectedWindow = oneOf(blob.window, Object.values(Window))
    if (selectedWindow) filtersStore.setWindow(selectedWindow)
    const start = toDate(blob.start)
    const end = toDate(blob.end)
    if (start && end && start < end) {
      filtersStore.enableCustomMode()
      filtersStore.setCustomRange(start, end)
    }
    const severity = oneOf(blob.severity, Object.values(SeverityFilter))
    if (severity) filtersStore.setSeverity(severity)
    const granularity = oneOf(blob.granularity, Object.values(Granularity))
    if (granularity) filtersStore.setGranularity(granularity)
    const compare = oneOf(blob.compare, Object.values(Compare))
    const compareStart = toDate(blob.compareStart)
    const compareEnd = toDate(blob.compareEnd)
    if (compare === Compare.CUSTOM) {
      if (compareStart && compareEnd && compareStart < compareEnd) {
        filtersStore.setCompareRange(compareStart, compareEnd)
      }
    } else if (compare) {
      filtersStore.setCompare(compare)
    }
    const autoRefresh = oneOf(
      blob.autoRefresh,
      AUTO_REFRESH_OPTIONS.map((option) => option.value),
    )
    if (autoRefresh !== null) filtersStore.setAutoRefresh(autoRefresh)
    const tab = oneOf(blob.tab, Object.values(TabKey))
    if (tab) tabsStore.setActiveTab(tab)
  }

  async function restore() {
    try {
      const session = await api.monitoring.getSessionInfo()
      storageKey.value = `monitoring-settings:${session.deployment_id}`
      const blob = readStorage(storageKey.value)
      if (blob) apply(blob)
    } catch {
      storageKey.value = null
    } finally {
      isReady.value = true
    }
  }

  watch(snapshot, (value) => {
    if (storageKey.value) writeStorage(storageKey.value, value)
  })

  return {
    isReady,
    restore,
  }
})
