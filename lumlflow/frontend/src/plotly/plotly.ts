type PlotlyModule = typeof import('plotly.js-dist')

let modulePromise: Promise<PlotlyModule> | null = null

export function loadPlotly(): Promise<PlotlyModule> {
  modulePromise ??= import('plotly.js-dist').then((imported) => imported.default ?? imported)
  return modulePromise
}

export function readCssVar(name: string, fallback: string): string {
  if (typeof window === 'undefined') return fallback
  const value = getComputedStyle(document.body).getPropertyValue(name).trim()
  return value || fallback
}

export function resolveColor(value: string, fallback = '#94a3b8'): string {
  const match = /^var\((--[\w-]+)\)$/.exec(value.trim())
  return match ? readCssVar(match[1], fallback) : value
}
