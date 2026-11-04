import { getArtifactColorByIndex } from '@/helpers/colors'
import { readCssVar, resolveColor } from './plotly'

export function baseChartLayout(): Record<string, unknown> {
  return {
    paper_bgcolor: 'transparent',
    plot_bgcolor: 'transparent',
    margin: { l: 36, r: 12, t: 8, b: 28 },
    showlegend: false,
    font: {
      family: 'Inter, sans-serif',
      size: 11,
      color: readCssVar('--p-text-muted-color', '#6b7280'),
    },
    xaxis: {
      showgrid: false,
      zeroline: false,
      linecolor: readCssVar('--p-content-border-color', '#e5e7eb'),
    },
    yaxis: {
      gridcolor: readCssVar('--p-content-border-color', '#e5e7eb'),
      zeroline: false,
      automargin: true,
    },
  }
}

export function chartColor(index: number): string {
  return resolveColor(getArtifactColorByIndex(index))
}

export function chartPalette(count: number): string[] {
  return Array.from({ length: count }, (_, index) => chartColor(index))
}
