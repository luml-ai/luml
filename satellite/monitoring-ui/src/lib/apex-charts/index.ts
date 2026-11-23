import type { ApexOptions } from 'apexcharts'

export const getBaseChartOptions = (): ApexOptions => ({
  chart: {
    toolbar: { show: false },
    zoom: { enabled: false },
    fontFamily: 'Inter, sans-serif',
    background: 'transparent',
    accessibility: { keyboard: { enabled: false } },
  },
  grid: {
    borderColor: 'var(--p-content-border-color)',
  },
  dataLabels: {
    enabled: false,
  },
  colors: ['var(--p-primary-color)'],
})

export interface LineChartOptionsParams {
  borderColor: string
  gridColor: string
  textColor: string
  isDark: boolean
}

export const getLineChartOptions = (params: LineChartOptionsParams): ApexOptions => ({
  ...getBaseChartOptions(),
  chart: {
    ...getBaseChartOptions().chart,
    animations: { enabled: false },
    foreColor: params.textColor,
  },
  stroke: {
    curve: 'straight',
    width: 2,
  },
  grid: {
    borderColor: params.gridColor,
    strokeDashArray: 0,
    xaxis: { lines: { show: false } },
    yaxis: { lines: { show: true } },
    padding: { top: 0, right: 8, bottom: 0, left: 8 },
  },
  legend: {
    show: false,
  },
  xaxis: {
    type: 'datetime',
    axisBorder: { show: true, color: params.borderColor, height: 2 },
    axisTicks: { show: false },
    crosshairs: { stroke: { color: params.borderColor, dashArray: 0 } },
    tooltip: { enabled: false },
    labels: {
      datetimeUTC: false,
      style: { colors: params.textColor, fontSize: '12px' },
    },
  },
  yaxis: {
    labels: {
      style: { colors: params.textColor, fontSize: '12px' },
    },
  },
  tooltip: {
    shared: true,
    intersect: false,
    theme: params.isDark ? 'dark' : 'light',
    x: { format: 'dd MMM HH:mm' },
  },
})
