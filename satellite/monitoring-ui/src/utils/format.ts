const integerFormat = new Intl.NumberFormat('en-US')

export function formatInteger(value: number): string {
  return integerFormat.format(value)
}

export function formatPercent(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}%`
}

export function formatPercentPoints(ratio: number): string {
  return `${(ratio * 100).toFixed(1)}pp`
}

export function formatMs(value: number): string {
  return `${Math.round(value)} ms`
}

export function formatOptional(
  value: number | null | undefined,
  formatter: (value: number) => string,
): string {
  return value == null ? '—' : formatter(value)
}
