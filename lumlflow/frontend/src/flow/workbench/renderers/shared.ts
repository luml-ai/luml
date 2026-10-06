import type { ParamValue } from '../model/types'

export type RenderDensity = 'canvas' | 'notebook' | 'drawer'

export function bodyMaxClass(density?: RenderDensity): string {
  switch (density) {
    case 'notebook':
      return 'max-h-44'
    case 'drawer':
      return 'max-h-[30rem]'
    default:
      return 'max-h-56'
  }
}

export function chartHeight(density?: RenderDensity): number {
  switch (density) {
    case 'notebook':
      return 120
    case 'drawer':
      return 220
    default:
      return 150
  }
}

export const CHART_PALETTE = ['#2563eb', '#d97706', '#0d9488', '#dc2626', '#7c3aed']

export function seriesColor(index: number): string {
  return CHART_PALETTE[index % CHART_PALETTE.length]
}

export function formatParam(value: ParamValue): string {
  if (value === null) return 'null'
  if (Array.isArray(value)) return `[${value.map(formatParam).join(', ')}]`
  return String(value)
}
