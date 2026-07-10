import { mount } from '@vue/test-utils'
import { describe, it, expect } from 'vitest'
import ForecastChart from '../ForecastChart.vue'
import type { ForecastingChart } from '@/lib/data-processing/interfaces'

const chartWithFit: ForecastingChart = {
  split_date: '2020-03-01',
  series: {
    sales: {
      actuals: [
        { date: '2020-01-01', value: 10 },
        { date: '2020-02-01', value: 12 },
        { date: '2020-03-01', value: 14 },
        { date: '2020-04-01', value: 16 },
      ],
      test_fit: [
        { date: '2020-03-01', value: 13, lower: 12, upper: 14 },
        { date: '2020-04-01', value: 15, lower: 14, upper: 16 },
      ],
    },
  },
}

function mountChart(chart: ForecastingChart) {
  return mount(ForecastChart, {
    props: { chart, targetCol: 'sales' },
    global: { stubs: { apexchart: true } },
  })
}

function legendLabels(wrapper: ReturnType<typeof mountChart>): string[] {
  return wrapper.findAll('[data-testid="role-legend-item"]').map((item) => item.text())
}

describe('ForecastChart legend', () => {
  it('distinguishes actual values from the model test fit and its confidence bounds', () => {
    const labels = legendLabels(mountChart(chartWithFit))
    expect(labels).toEqual([
      'Train (actual)',
      'Test (actual)',
      'Test fit (model)',
      'Confidence bounds',
    ])
  })

  it('omits roles that are not drawn', () => {
    const noFit: ForecastingChart = {
      split_date: null,
      series: { sales: { actuals: [{ date: '2020-01-01', value: 10 }] } },
    }
    expect(legendLabels(mountChart(noFit))).toEqual(['Train (actual)'])
  })

  it('labels the forecast segment when a future preview exists', () => {
    const withFuture: ForecastingChart = {
      ...chartWithFit,
      series: {
        sales: {
          ...chartWithFit.series.sales,
          future: [{ date: '2020-05-01', value: 18, lower: 17, upper: 19 }],
        },
      },
    }
    expect(legendLabels(mountChart(withFuture))).toContain('Forecast')
  })
})
