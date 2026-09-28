export function formatCost(seconds: number): string {
  if (seconds < 0.1) return '<0.1s'
  if (seconds < 60) return `${seconds < 10 ? seconds.toFixed(1) : Math.round(seconds)}s`
  const minutes = Math.floor(seconds / 60)
  if (minutes < 60) return `${minutes}m ${Math.round(seconds % 60)}s`
  return `${Math.floor(minutes / 60)}h ${minutes % 60}m`
}

export function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`
  const units = ['KB', 'MB', 'GB', 'TB']
  let value = bytes
  let unit = ''
  for (const next of units) {
    value /= 1024
    unit = next
    if (value < 1024) break
  }
  return `${value >= 100 ? Math.round(value) : value.toFixed(1)} ${unit}`
}

export type MetricValue = number | 'nan' | 'inf' | '-inf'

export function formatMetric(value: MetricValue): string {
  if (typeof value === 'string') return value
  if (Number.isNaN(value)) return 'nan'
  if (value === Number.POSITIVE_INFINITY) return 'inf'
  if (value === Number.NEGATIVE_INFINITY) return '-inf'
  if (Number.isInteger(value)) return String(value)
  if (value !== 0 && Math.abs(value) < 1e-3) return value.toExponential(1)
  if (Math.abs(value) >= 100) return value.toFixed(1)
  if (Math.abs(value) >= 1) return value.toFixed(2)
  return value.toFixed(3)
}

export function formatCount(count: number, noun: string): string {
  return `${count} ${noun}${count === 1 ? '' : 's'}`
}
