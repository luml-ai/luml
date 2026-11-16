import {
  SectionState,
  type ClassProbabilityDrift,
  type ClassShift,
  type ConfidenceBlock,
  type OutputDriftResponse,
} from '@/api/monitoring/interfaces'
import {
  CLASS_SHIFT_CRITICAL_THRESHOLD,
  CLASS_SHIFT_WARNING_THRESHOLD,
} from '@/constants/output-drift'
import type { EmptyStateContent } from '@/types/empty'
import type { ClassDriftRow } from '@/types/output-drift'
import { formatPsiLabel, getPsiSeverity } from '@/utils/drift'
import {
  formatDecimal,
  formatInteger,
  formatOptional,
  formatPercent,
  formatPercentPoints,
  getSeverityByThresholds,
} from '@/utils/format'

export function formatPredictionsCount(count: number): string {
  return `${formatInteger(count)} ${count === 1 ? 'prediction' : 'predictions'} in the window`
}

export function getOutputPsiLabel(name: string | null | undefined): string {
  return name ? `PSI · ${name}` : 'PSI'
}

export function formatLowConfidence(confidence: ConfidenceBlock): string | null {
  if (confidence.low_confidence_rate == null || confidence.low_confidence_threshold == null) {
    return null
  }
  return `${formatPercent(confidence.low_confidence_rate)} of predictions below the training q05 (${formatPercent(confidence.low_confidence_threshold)})`
}

export function getProbabilityRows(perClass: ClassProbabilityDrift[]): ClassDriftRow[] {
  return perClass.map((item) => ({
    label: item.label,
    detail: `mean p ${formatOptional(item.mean, formatDecimal)}`,
    value: formatPsiLabel(item.psi),
    severity: getPsiSeverity(item.psi),
  }))
}

export function formatClassShift(delta: number): string {
  const magnitude = formatPercentPoints(Math.abs(delta))
  if (parseFloat(magnitude) === 0) return magnitude
  return `${delta > 0 ? '+' : '-'}${magnitude}`
}

export function getTopChangedRows(shifts: ClassShift[]): ClassDriftRow[] {
  return shifts.map((shift) => ({
    label: shift.label,
    detail: `${formatPercent(shift.reference)} → ${formatPercent(shift.current)}`,
    value: formatClassShift(shift.delta),
    severity: getSeverityByThresholds(
      Math.abs(shift.delta),
      CLASS_SHIFT_WARNING_THRESHOLD,
      CLASS_SHIFT_CRITICAL_THRESHOLD,
    ),
  }))
}

export function getOutputDriftEmptyState(
  outputDrift: OutputDriftResponse,
): EmptyStateContent | null {
  if (outputDrift.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Output drift unavailable',
      detail: 'The monitoring store could not provide output drift for this window.',
    }
  }
  if (outputDrift.state === SectionState.EMPTY) {
    return {
      title: 'No output drift computed yet',
      detail: 'The worker has not materialized output drift for this window yet.',
    }
  }
  if (!outputDrift.count) {
    return {
      title: 'No predictions in this window',
      detail: 'Output drift needs a reference profile and logged predictions in this window.',
    }
  }
  return null
}
