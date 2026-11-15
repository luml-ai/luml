import { Severity } from '@/api/monitoring/interfaces'
import { PSI_SCALE_MAX } from '@/constants/drift'

const psiFormat = new Intl.NumberFormat('en-US', { maximumFractionDigits: 3 })

export function formatPsi(psi: number): string {
  return psiFormat.format(psi)
}

export function getPsiProgress(psi: number): number {
  return Math.min(100, Math.max(0, Math.round((psi / PSI_SCALE_MAX) * 100)))
}

export function getPsiBarColor(severity: Severity): string {
  if (severity === Severity.CRITICAL) return '{red.500}'
  if (severity === Severity.WARNING) return '{orange.500}'
  return '{primary.color}'
}
