import {
  SectionState,
  type DataQualityFeatureRow,
  type DataQualityResponse,
} from '@/api/monitoring/interfaces'
import { SEVERITY_ORDER, UNKNOWN_SEVERITY_ORDER } from '@/constants/alerts'
import type { EmptyStateContent } from '@/types/empty'
import { formatOptional, formatPercent } from '@/utils/format'

export function formatRate(value: number | null | undefined): string {
  return formatOptional(value, formatPercent)
}

export function getRangeLabel(row: DataQualityFeatureRow): string {
  if (row.range_violation_rate != null)
    return `${formatPercent(row.range_violation_rate)} out of range`
  if (row.unseen_category_rate != null) return `${formatPercent(row.unseen_category_rate)} unseen`
  return formatRate(row.range_unseen_rate)
}

export function getStatusSortValue(row: DataQualityFeatureRow): string {
  return String(SEVERITY_ORDER[row.status] ?? UNKNOWN_SEVERITY_ORDER)
}

export function getDataQualityEmptyState(
  dataQuality: DataQualityResponse,
): EmptyStateContent | null {
  if (dataQuality.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Data quality unavailable',
      detail: 'The monitoring store could not provide data quality for this window.',
    }
  }
  if (dataQuality.state === SectionState.EMPTY) {
    return {
      title: 'No data quality results yet',
      detail: 'The worker has not materialized data quality for this window yet.',
    }
  }
  if (!dataQuality.features.length) {
    return {
      title: 'No features to check in this window',
      detail: 'None of the monitored features match the current filters.',
    }
  }
  return null
}
