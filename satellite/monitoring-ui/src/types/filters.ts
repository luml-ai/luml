import type { Compare, SeverityFilter, Window } from '@/api/monitoring/interfaces'

export enum AutoRefresh {
  OFF = 0,
  S30 = 30,
  M1 = 60,
  M5 = 300,
}

export interface FilterOption<T> {
  label: string
  value: T
}

export type WindowOption = FilterOption<Window>
export type AutoRefreshOption = FilterOption<AutoRefresh>
export type SeverityOption = FilterOption<SeverityFilter>
export type CompareOption = FilterOption<Compare>
