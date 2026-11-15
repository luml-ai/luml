import { Compare, SeverityFilter, Window } from '@/api/monitoring/interfaces'
import {
  AutoRefresh,
  type AutoRefreshOption,
  type CompareOption,
  type SeverityOption,
  type WindowOption,
} from '@/types/filters'

export const WINDOW_OPTIONS: WindowOption[] = [
  { label: '24h', value: Window.H24 },
  { label: '7d', value: Window.D7 },
  { label: '30d', value: Window.D30 },
]

export const AUTO_REFRESH_OPTIONS: AutoRefreshOption[] = [
  { label: 'Off', value: AutoRefresh.OFF },
  { label: '30s', value: AutoRefresh.S30 },
  { label: '1m', value: AutoRefresh.M1 },
  { label: '5m', value: AutoRefresh.M5 },
]

export const SEVERITY_OPTIONS: SeverityOption[] = [
  { label: 'All', value: SeverityFilter.ALL },
  { label: 'Warning', value: SeverityFilter.WARNING },
  { label: 'Critical', value: SeverityFilter.CRITICAL },
]

export const COMPARE_OPTIONS: CompareOption[] = [
  { label: 'Off', value: Compare.OFF },
  { label: 'Previous', value: Compare.PREVIOUS },
  { label: 'Custom', value: Compare.CUSTOM },
]

export const RETENTION_DAYS = 30
