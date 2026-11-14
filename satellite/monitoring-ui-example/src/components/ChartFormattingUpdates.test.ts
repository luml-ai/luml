import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import VueApexCharts from 'vue3-apexcharts'
import type ApexCharts from 'apexcharts'
import DistributionChart from './feature-drift/DistributionChart.vue'

describe('chart formatting after refresh', () => {
  afterEach(() => vi.restoreAllMocks())

  it('preserves axis and tooltip callbacks when the chart wrapper updates its options', async () => {
    const wrapper = mount(DistributionChart, {
      props: {
        distribution: {
          kind: 'numeric',
          bins: [{ label: '0–1', reference: 0.5, current: 0.3 }],
        },
      },
      global: { components: { apexchart: VueApexCharts } },
    })
    // the wrapper exposes its constructor before initializing the chart on the next tick
    const chartPrototype = (window as typeof window & { ApexCharts: typeof ApexCharts }).ApexCharts
      .prototype
    const resolveChart = function (this: ApexCharts) {
      return Promise.resolve(this)
    }
    vi.spyOn(chartPrototype, 'render').mockImplementation(resolveChart)
    vi.spyOn(chartPrototype, 'destroy').mockImplementation(() => {})
    vi.spyOn(chartPrototype, 'updateSeries').mockImplementation(resolveChart)
    const updateOptions = vi.spyOn(chartPrototype, 'updateOptions').mockImplementation(resolveChart)
    await flushPromises()
    await wrapper.setProps({
      distribution: {
        kind: 'numeric',
        bins: [{ label: '0.123456–1.234567', reference: 0.12345678, current: 0.3 }],
      },
    })
    await flushPromises()

    expect(updateOptions).toHaveBeenCalled()
    const options = updateOptions.mock.calls.at(-1)![0] as {
      yaxis: { labels: { formatter: (value: number) => string } }
      tooltip: { y: { formatter: (value: number) => string } }
      xaxis: { categories: string[] }
    }
    expect(options.yaxis.labels.formatter).toEqual(expect.any(Function))
    expect(options.yaxis.labels.formatter(0.12345678)).toBe('12.346%')
    expect(options.tooltip.y.formatter(0.5)).toBe('50%')
    expect(options.xaxis.categories).toEqual(['0.123–1.235'])
    wrapper.unmount()
  })
})
