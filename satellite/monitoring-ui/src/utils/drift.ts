import {
  SectionState,
  Severity,
  type FeatureDistribution,
  type FeatureDriftResponse,
  type MultivariatePanel,
  type PcaPoint,
} from '@/api/monitoring/interfaces'
import {
  PCA_RANGE_PADDING,
  PCA_RANGE_QUANTILE,
  PSI_ATTENTION_THRESHOLD,
  PSI_CRITICAL_THRESHOLD,
  PSI_SCALE_MAX,
  PSI_WARNING_THRESHOLD,
} from '@/constants/drift'
import { SEVERITY_COLORS } from '@/constants/alerts'
import type { EmptyStateContent } from '@/types/empty'
import type { MultivariateMetric, PcaBounds, PcaRange } from '@/types/drift'
import { formatDecimal, formatOptional, formatPercent } from '@/utils/format'

const psiFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 })

export function formatPsi(psi: number): string {
  return psiFormat.format(psi)
}

export function formatPsiValue(psi: number | null | undefined): string {
  return formatOptional(psi, formatDecimal)
}

export function getPsiSeverity(psi: number): Severity {
  if (psi > PSI_CRITICAL_THRESHOLD) return Severity.CRITICAL
  if (psi >= PSI_WARNING_THRESHOLD) return Severity.WARNING
  return Severity.OK
}

export function formatPsiLabel(psi: number | null | undefined): string {
  return `PSI ${formatPsiValue(psi)}`
}

export function getPsiProgress(psi: number): number {
  return Math.min(100, Math.max(0, Math.round((psi / PSI_SCALE_MAX) * 100)))
}

export function getPsiBarColor(severity: Severity): string {
  return SEVERITY_COLORS[severity] ?? SEVERITY_COLORS[Severity.OK]
}

export function getDistributionCategories(distribution: FeatureDistribution): string[] {
  return distribution.bins.map((bin) => bin.label)
}

export function getDistributionSeries(distribution: FeatureDistribution) {
  const hasCurrent = distribution.bins.some((bin) => bin.current != null)
  const series = [
    { name: 'Reference', data: distribution.bins.map((bin) => bin.reference ?? 0) },
    { name: 'Current', data: distribution.bins.map((bin) => bin.current ?? 0) },
  ]
  return hasCurrent ? series : series.slice(0, 1)
}

export function getFeatureDriftEmptyState(
  featureDrift: FeatureDriftResponse,
): EmptyStateContent | null {
  if (featureDrift.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Feature drift unavailable',
      detail: 'The monitoring store could not provide feature drift for this window.',
    }
  }
  if (featureDrift.state === SectionState.EMPTY) {
    return {
      title: 'No feature drift computed yet',
      detail: 'The worker has not materialized feature drift for this window yet.',
    }
  }
  return null
}

export const NO_RANKED_FEATURES_STATE: EmptyStateContent = {
  title: 'No features to rank',
  detail: 'Feature drift needs a reference profile and live traffic in this window.',
}

export function getMultivariateEmptyState(
  multivariate: MultivariatePanel,
): EmptyStateContent | null {
  if (multivariate.state === SectionState.UNAVAILABLE) {
    return {
      title: 'Multivariate drift unavailable',
      detail: 'The monitoring store could not provide multivariate drift for this window.',
    }
  }
  if (multivariate.state === SectionState.EMPTY) {
    return {
      title: 'No multivariate drift computed yet',
      detail: 'Multivariate drift needs a reference PCA basis and live traffic in this window.',
    }
  }
  return null
}

export function countPsiAttention(multivariate: MultivariatePanel): number {
  return multivariate.feature_psi.filter((feature) => feature.psi >= PSI_ATTENTION_THRESHOLD).length
}

export function getShiftMetricLabel(metric: string | null | undefined): string {
  if (!metric) return 'Shift distance'
  const label = metric.replace(/_/g, ' ')
  return label.charAt(0).toUpperCase() + label.slice(1)
}

export function getMultivariateMetrics(multivariate: MultivariatePanel): MultivariateMetric[] {
  const explainedVariance = multivariate.explained_variance.length
    ? multivariate.explained_variance.reduce((sum, value) => sum + value, 0)
    : null
  return [
    {
      label: getShiftMetricLabel(multivariate.shift_metric),
      value: formatOptional(multivariate.shift_value, (value) =>
        `${value.toFixed(2)} ${multivariate.shift_unit ?? ''}`.trim(),
      ),
    },
    {
      label: 'Spread vs training',
      value: formatOptional(multivariate.dispersion_ratio, (value) => `${value.toFixed(2)}×`),
    },
    {
      label: 'Outlier rate',
      value: formatOptional(multivariate.outlier_rate, formatPercent),
    },
    {
      label: 'Per-feature PSI',
      value: `${countPsiAttention(multivariate)} / ${multivariate.feature_psi.length}`,
    },
    {
      label: 'Explained variance',
      value: formatOptional(explainedVariance, formatPercent),
    },
  ]
}

const pcaTickFormat = new Intl.NumberFormat('en-US', {
  minimumFractionDigits: 3,
  maximumFractionDigits: 3,
})

export function formatPcaTick(value: number): string {
  return pcaTickFormat.format(value)
}

function getQuantile(sorted: number[], q: number): number {
  const index = (sorted.length - 1) * q
  const lower = Math.floor(index)
  const upper = Math.ceil(index)
  return sorted[lower] + (sorted[upper] - sorted[lower]) * (index - lower)
}

function getPcaRange(values: number[], ellipseValues: number[]): PcaRange {
  const sorted = [...values].sort((a, b) => a - b)
  const candidates = [...ellipseValues]
  if (sorted.length) {
    candidates.push(getQuantile(sorted, PCA_RANGE_QUANTILE))
    candidates.push(getQuantile(sorted, 1 - PCA_RANGE_QUANTILE))
  }
  if (!candidates.length) return { min: -1, max: 1 }
  let min = Math.min(...candidates)
  let max = Math.max(...candidates)
  if (min === max) {
    min -= 1
    max += 1
  }
  const padding = (max - min) * PCA_RANGE_PADDING
  return { min: min - padding, max: max + padding }
}

export function getPcaBounds(points: PcaPoint[], ellipses: PcaPoint[]): PcaBounds {
  return {
    x: getPcaRange(
      points.map((point) => point.x),
      ellipses.map((point) => point.x),
    ),
    y: getPcaRange(
      points.map((point) => point.y),
      ellipses.map((point) => point.y),
    ),
  }
}

export function isPcaPointInBounds(point: PcaPoint, bounds: PcaBounds): boolean {
  return (
    point.x >= bounds.x.min &&
    point.x <= bounds.x.max &&
    point.y >= bounds.y.min &&
    point.y <= bounds.y.max
  )
}

export function clampPcaPoint(point: PcaPoint, bounds: PcaBounds): PcaPoint {
  return {
    x: Math.min(bounds.x.max, Math.max(bounds.x.min, point.x)),
    y: Math.min(bounds.y.max, Math.max(bounds.y.min, point.y)),
  }
}

export function formatPinnedPoints(count: number): string {
  return `${count} ${count === 1 ? 'point' : 'points'} beyond range, pinned to the edge`
}

export function toPcaChartPoints(points: PcaPoint[]): [number, number][] {
  return points.map((point) => [point.x, point.y])
}
