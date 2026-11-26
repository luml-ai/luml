import type { Severity } from '@/api/monitoring/interfaces'

export interface ClassDriftRow {
  label: string
  detail: string
  value: string
  severity: Severity
}
