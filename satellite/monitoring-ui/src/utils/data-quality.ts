import {
  SectionState,
  Severity,
  type DataQualityFeatureRow,
  type DataQualityResponse,
  type InvalidValueSummary,
} from '@/api/monitoring/interfaces'
import { SEVERITY_ORDER, UNKNOWN_SEVERITY_ORDER } from '@/constants/alerts'
import { DATA_QUALITY_THRESHOLDS, QualityCheck } from '@/constants/data-quality'
import type { EmptyStateContent } from '@/types/empty'
import type { AlertStatsRow } from '@/types/alerts'
import { getAlertValueColor } from '@/utils/alerts'
import { formatPreciseValue } from '@/utils/charts'
import {
  formatInteger,
  formatOptional,
  formatPercent,
  formatPercentPoints,
  formatSignedDelta,
} from '@/utils/format'

export function formatRate(value: number | null | undefined): string {
  return formatOptional(value, formatPercent)
}

export function getRangeLabel(row: DataQualityFeatureRow): string {
  if (row.range_violation_rate != null)
    return `${formatPercent(row.range_violation_rate)} out of range`
  if (row.unseen_category_rate != null) return `${formatPercent(row.unseen_category_rate)} unseen`
  return formatRate(row.range_unseen_rate)
}

export function getRangeCheck(row: DataQualityFeatureRow): QualityCheck {
  if (row.range_violation_rate != null) return QualityCheck.RANGE_VIOLATION
  if (row.unseen_category_rate != null) return QualityCheck.UNSEEN_CATEGORY
  return row.kind === 'categorical' ? QualityCheck.UNSEEN_CATEGORY : QualityCheck.RANGE_VIOLATION
}

export function getCheckSeverity(
  rate: number | null | undefined,
  check: QualityCheck,
): Severity | null {
  if (rate == null) return null
  const { warning, critical } = DATA_QUALITY_THRESHOLDS[check]
  if (rate > critical) return Severity.CRITICAL
  if (rate > warning) return Severity.WARNING
  return null
}

export function getCheckColor(
  rate: number | null | undefined,
  check: QualityCheck,
): string | undefined {
  const severity = getCheckSeverity(rate, check)
  return severity ? getAlertValueColor(severity) : undefined
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

export function formatRateDelta(delta: number | null | undefined): string | null {
  return delta == null ? null : formatSignedDelta(delta, formatPercentPoints)
}

function formatCheckShare(
  row: DataQualityFeatureRow,
  rate: number | null | undefined,
  count: number | undefined,
): string {
  if (count == null) return formatRate(rate)
  const counted =
    row.checked != null
      ? `${formatInteger(count)} of ${formatInteger(row.checked)}`
      : formatInteger(count)
  return `${formatRate(rate)} · ${counted}`
}

export function getDataQualityCheckRows(row: DataQualityFeatureRow): AlertStatsRow[] {
  const invalid = row.invalid
  const rows: AlertStatsRow[] = [
    {
      label: 'Missing',
      value: formatCheckShare(row, row.missing_rate, invalid?.missing_count),
      color: getCheckColor(row.missing_rate, QualityCheck.MISSING),
    },
    {
      label: 'Type errors',
      value: formatCheckShare(row, row.type_error_rate, invalid?.type_mismatch_count),
      color: getCheckColor(row.type_error_rate, QualityCheck.TYPE_MISMATCH),
    },
  ]
  if (row.kind === 'categorical') {
    rows.push({
      label: 'Unseen categories',
      value: formatCheckShare(row, row.unseen_category_rate, invalid?.unseen_category_count),
      color: getCheckColor(row.unseen_category_rate, QualityCheck.UNSEEN_CATEGORY),
    })
  } else {
    rows.push({
      label: 'Out of range',
      value: formatCheckShare(row, row.range_violation_rate, invalid?.range_violation_count),
      color: getCheckColor(row.range_violation_rate, QualityCheck.RANGE_VIOLATION),
    })
  }
  return rows
}

export function getRangeViolationRows(invalid: InvalidValueSummary): AlertStatsRow[] {
  return [
    {
      label: 'Reference bounds',
      value: `${formatPreciseValue(invalid.reference_min)} … ${formatPreciseValue(invalid.reference_max)}`,
    },
    {
      label: 'Observed extremes',
      value: `${formatPreciseValue(invalid.observed_min)} … ${formatPreciseValue(invalid.observed_max)}`,
    },
    { label: 'Below minimum', value: formatInteger(invalid.below_min) },
    { label: 'Above maximum', value: formatInteger(invalid.above_max) },
  ]
}

export function getUnseenCategoryRows(invalid: InvalidValueSummary): AlertStatsRow[] {
  return invalid.unseen_categories.map((category) => ({
    label: category.value,
    value: formatInteger(category.count),
  }))
}

export function getUnseenCategoriesNote(invalid: InvalidValueSummary): string {
  const hidden = Math.max(0, invalid.unseen_distinct - invalid.unseen_categories.length)
  const known =
    invalid.reference_categories != null
      ? ` The training reference holds ${formatInteger(invalid.reference_categories)} ${invalid.reference_categories === 1 ? 'category' : 'categories'}.`
      : ''
  const more =
    hidden > 0
      ? ` ${formatInteger(hidden)} more distinct ${hidden === 1 ? 'value' : 'values'} not listed.`
      : ''
  return `${formatInteger(invalid.unseen_distinct)} distinct ${invalid.unseen_distinct === 1 ? 'value' : 'values'} the training reference never saw.${known}${more}`
}

export function getTypeErrorRows(invalid: InvalidValueSummary): AlertStatsRow[] {
  return Object.entries(invalid.observed_types).map(([type, count]) => ({
    label: type,
    value: formatInteger(count),
  }))
}

export function hasInvalidValues(row: DataQualityFeatureRow): boolean {
  return [row.missing_rate, row.type_error_rate, row.range_unseen_rate].some(
    (rate) => (rate ?? 0) > 0,
  )
}
