export const PSI_WARNING_THRESHOLD = 0.1

export const PSI_CRITICAL_THRESHOLD = 0.25

export const PSI_SCALE_MAX = PSI_CRITICAL_THRESHOLD

export const DRIFT_CHART_ASPECT_RATIO = '585 / 225'

export const STATUS_TAG_TOKENS = { padding: '2px 4px', borderRadius: '4px' }

export const PCA_AXIS_TICKS = 5

export const PCA_RANGE_QUANTILE = 0.01

export const PCA_RANGE_PADDING = 0.05

export const PCA_LEGEND_ITEMS = [
  { key: 'reference', label: 'Reference (training)' },
  { key: 'current', label: 'Logged (current window)' },
  { key: 'pinned', label: 'Beyond range' },
]

export const PCA_PROJECTED_COMPONENTS = 2

export const PCA_SERIES_COLORS = {
  referenceEllipse: '--p-surface-600',
  referencePoint: '--p-surface-500',
  current: '--p-orange-500',
  pinned: '--p-red-500',
  pinnedStroke: '--p-red-700',
}

export const PCA_SERIES_INDEX = {
  referenceEllipse: 0,
  currentEllipse: 1,
  reference: 2,
  current: 3,
  pinned: 4,
}
