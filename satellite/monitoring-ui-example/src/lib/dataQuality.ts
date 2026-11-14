/**
 * Spec alert thresholds for the input-quality checks; a rate breaches a bound when it is
 * strictly above it. Shared so the table and the detail panel colour the same numbers.
 */
export const DATA_QUALITY_THRESHOLDS = {
  missing: { warning: 0.01, critical: 0.05 },
  type_mismatch: { warning: 0, critical: 0.01 },
  range_violation: { warning: 0.01, critical: 0.05 },
  unseen_category: { warning: 0, critical: 0.01 },
} as const

export type QualityCheck = keyof typeof DATA_QUALITY_THRESHOLDS

/** 'critical' | 'warn' for a breached rate, null when it is within bounds or unknown. */
export function rateClass(value: number | null | undefined, check: QualityCheck): string | null {
  if (value == null) return null
  const { warning, critical } = DATA_QUALITY_THRESHOLDS[check]
  if (value > critical) return 'critical'
  if (value > warning) return 'warn'
  return null
}
