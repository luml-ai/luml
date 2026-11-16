export interface MultivariateMetric {
  label: string
  value: string
}

export interface PcaRange {
  min: number
  max: number
}

export interface PcaBounds {
  x: PcaRange
  y: PcaRange
}
