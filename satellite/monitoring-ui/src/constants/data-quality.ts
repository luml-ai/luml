export const DATA_QUALITY_COLUMN_WIDTHS = {
  feature: 190,
  missing: 130,
  typeErrors: 150,
  range: 250,
  status: 161,
}

export enum QualityCheck {
  MISSING = 'missing',
  TYPE_MISMATCH = 'type_mismatch',
  RANGE_VIOLATION = 'range_violation',
  UNSEEN_CATEGORY = 'unseen_category',
}

export const DATA_QUALITY_THRESHOLDS: Record<QualityCheck, { warning: number; critical: number }> =
  {
    [QualityCheck.MISSING]: { warning: 0.01, critical: 0.05 },
    [QualityCheck.TYPE_MISMATCH]: { warning: 0, critical: 0.01 },
    [QualityCheck.RANGE_VIOLATION]: { warning: 0.01, critical: 0.05 },
    [QualityCheck.UNSEEN_CATEGORY]: { warning: 0, critical: 0.01 },
  }
