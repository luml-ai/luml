import type { ApexOptions } from 'apexcharts'

export const getRadialBarOptions = (): ApexOptions => ({
  chart: {
    type: 'radialBar',
  },
  plotOptions: {
    radialBar: {
      startAngle: -90,
      endAngle: 90,
      dataLabels: {
        name: {
          show: true,
          color: 'var(--p-text-muted-color)',
          offsetY: 20,
          // @ts-expect-error formatter is not present in ApexOptions name dataLabels typings
          formatter: () => 'Total score',
        },
        value: {
          fontSize: '32px',
          color: 'var(--p-text-color)',
          offsetY: -20,
        },
      },
      hollow: {
        size: '50%',
      },
    },
  },
  colors: ['var(--p-primary-color)'],
})

export const getBarOptions = (categories: string[]): ApexOptions => ({
  chart: {
    type: 'bar',
    fontFamily: 'Inter, sans-serif',
    toolbar: {
      show: false,
    },
  },
  dataLabels: {
    enabled: false,
    formatter: (val: number) => `${val}%`,
    style: {
      fontSize: '16px',
      fontFamily: 'Inter, Arial, sans-serif',
      colors: ['var(--p-card-background)'],
      fontWeight: 600,
    },
  },
  grid: {
    show: false,
  },
  labels: categories,
  plotOptions: {
    bar: {
      borderRadius: 4,
      horizontal: true,
      barHeight: '32px',
      colors: {
        ranges: [
          {
            from: 0,
            to: 100,
            color: 'var(--p-primary-color)',
          },
        ],
      },
    },
  },
  xaxis: {
    labels: {
      show: false,
    },
    axisBorder: {
      show: false,
    },
    axisTicks: {
      show: false,
    },
  },
  yaxis: {
    axisBorder: {
      show: false,
    },
    labels: {
      align: 'left',
      offsetX: -12,
      style: {
        fontSize: '16px',
        cssClass: 'bar-label',
      },
    },
  },
  tooltip: {
    enabled: false,
  },
})
