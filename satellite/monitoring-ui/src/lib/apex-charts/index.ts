import type { ApexOptions } from 'apexcharts'

export const getBaseChartOptions = (): ApexOptions => ({
  chart: {
    toolbar: { show: false },
    zoom: { enabled: false },
    fontFamily: 'Inter, sans-serif',
    background: 'transparent',
  },
  grid: {
    borderColor: 'var(--p-content-border-color)',
  },
  dataLabels: {
    enabled: false,
  },
  colors: ['var(--p-primary-color)'],
})
