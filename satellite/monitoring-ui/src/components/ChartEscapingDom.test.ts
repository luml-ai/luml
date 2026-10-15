import { afterEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount } from '@vue/test-utils'
import VueApexCharts from 'vue3-apexcharts'
import ClassShareChart from './output-drift/ClassShareChart.vue'
import DistributionChart from './feature-drift/DistributionChart.vue'

const payload = '<img src=x onerror="window.__pwned=1"> &lt;svg&gt;'
const points = [
  { t: '2026-08-18T14:00:00Z', value: 0.5 },
  { t: '2026-08-18T15:00:00Z', value: 0.4 },
]
const global = { components: { apexchart: VueApexCharts } }

type RenderedChart = {
  tooltip: {
    tooltipLabels: {
      drawSeriesTexts: (options: {
        i: number
        j: number
        shared: boolean
        ttItems: NodeListOf<Element>
      }) => void
    }
  }
}

describe('ApexCharts label HTML sinks', () => {
  afterEach(() => vi.unstubAllGlobals())

  function prepareChart() {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
  }

  it('renders malicious class names as literal legend and tooltip text', async () => {
    prepareChart()
    const wrapper = mount(ClassShareChart, {
      props: {
        series: [
          { key: 'c', label: payload, points },
          { key: 'd', label: 'cat', points },
        ],
      },
      global,
      attachTo: document.body,
    })
    try {
      await flushPromises()
      await vi.waitFor(() => expect(wrapper.find('.apexcharts-legend-text').exists()).toBe(true))
      expect(wrapper.get('.apexcharts-legend-text').text()).toBe(payload)
      const chart = (wrapper.getComponent(VueApexCharts).vm as unknown as { chart: RenderedChart })
        .chart
      chart.tooltip.tooltipLabels.drawSeriesTexts({
        i: 0,
        j: 0,
        shared: false,
        ttItems: wrapper.element.querySelectorAll('.apexcharts-tooltip-series-group'),
      })
      expect(wrapper.get('.apexcharts-tooltip-text-y-label').text()).toBe(`${payload}:`)
      expect(wrapper.find('img').exists()).toBe(false)
    } finally {
      wrapper.unmount()
    }
  })

  it('renders categories as literal SVG labels and tooltip titles', async () => {
    prepareChart()
    const wrapper = mount(DistributionChart, {
      props: {
        distribution: {
          kind: 'categorical',
          bins: [{ label: payload, reference: 0.5, current: 0.5 }],
        },
      },
      global,
      attachTo: document.body,
    })
    try {
      await flushPromises()
      await vi.waitFor(() => expect(wrapper.find('.apexcharts-xaxis-label').exists()).toBe(true))
      expect(wrapper.get('.apexcharts-xaxis-label tspan').text()).toBe(payload)
      const chart = (wrapper.getComponent(VueApexCharts).vm as unknown as { chart: RenderedChart })
        .chart
      chart.tooltip.tooltipLabels.drawSeriesTexts({
        i: 0,
        j: 0,
        shared: false,
        ttItems: wrapper.element.querySelectorAll('.apexcharts-tooltip-series-group'),
      })
      expect(wrapper.get('.apexcharts-tooltip-title').text()).toBe(payload)
      expect(wrapper.find('img').exists()).toBe(false)
    } finally {
      wrapper.unmount()
    }
  })
})
