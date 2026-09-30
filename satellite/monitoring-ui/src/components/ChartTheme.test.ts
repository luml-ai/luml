import { afterEach, beforeAll, describe, expect, it } from 'vitest'
import { defineComponent, h, type Component } from 'vue'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import type { Series } from '@/api/types'
import { applyTheme, initTheme, THEME_MESSAGE_TYPE, type Theme } from '@/lib/theme'
import ChartFrame from './ChartFrame.vue'
import SeriesChart from './SeriesChart.vue'
import DistributionChart from './feature-drift/DistributionChart.vue'
import ClassShareChart from './output-drift/ClassShareChart.vue'
import PredictionTrendChart from './output-drift/PredictionTrendChart.vue'

const ApexStub = {
  name: 'apexchart',
  props: ['type', 'height', 'options', 'series'],
  template: '<div class="apex" />',
}

const points = [
  { t: '2026-07-07T10:00:00Z', value: 0.2 },
  { t: '2026-07-07T11:00:00Z', value: 0.3 },
]
const series: Series = { key: 'requests', label: 'Requests', points, baseline: points }
const charts: { name: string; component: Component; props: Record<string, unknown> }[] = [
  { name: 'runtime comparison', component: SeriesChart, props: { series } },
  {
    name: 'feature and output distributions',
    component: DistributionChart,
    props: {
      distribution: {
        kind: 'categorical',
        bins: [{ label: 'yes', reference: 0.2, current: 0.3 }],
      },
    },
  },
  {
    name: 'class shares',
    component: ClassShareChart,
    props: { series: [series, { ...series, label: 'Other class' }] },
  },
  {
    name: 'prediction trend',
    component: PredictionTrendChart,
    props: {
      trend: ['p05', 'p95', 'median', 'mean'].map((key) => ({
        ...series,
        key: `prediction_${key}`,
      })),
    },
  },
]
const themes: { theme: Theme; color: string }[] = [
  { theme: 'light', color: '#334155' },
  { theme: 'dark', color: '#e2e8f0' },
]

interface ChartOptions {
  chart: { foreColor: string }
  tooltip: { theme: Theme }
  xaxis: { labels: { style: { colors: string } } }
  yaxis: { labels: { style: { colors: string } } }
}

enableAutoUnmount(afterEach)
beforeAll(() => initTheme())
afterEach(() => applyTheme('light'))

describe.each(charts)('$name chart theme', ({ component, props }) => {
  function renderChart() {
    return mount(
      defineComponent({
        setup: () => () =>
          h(ChartFrame, { title: 'Monitoring chart' }, {
            default: ({ height }: { height: number }) => h(component, { ...props, height }),
          }),
      }),
      { global: { stubs: { apexchart: ApexStub, teleport: true } } },
    )
  }

  it.each(themes)('uses readable legend and tooltip colors on first paint in $theme', ({ theme, color }) => {
    applyTheme(theme)
    const wrapper = renderChart()
    const options = wrapper.findComponent(ApexStub).props('options') as ChartOptions

    // apexcharts uses foreColor for legend labels and other default chart text
    expect(options.chart.foreColor).toBe(color)
    expect(options.tooltip.theme).toBe(theme)
    expect(options.xaxis.labels.style.colors).toBe('#94a3b8')
    expect(options.yaxis.labels.style.colors).toBe('#94a3b8')
    expect(wrapper.findComponent(ApexStub).props('series').length).toBeGreaterThan(1)
  })

  it('updates mounted card and full-screen legends and tooltips from platform theme messages', async () => {
    applyTheme('light')
    const wrapper = renderChart()
    await wrapper.find('[data-testid="chart-expand"]').trigger('click')
    const mountedCharts = wrapper.findAllComponents(ApexStub)
    expect(mountedCharts).toHaveLength(2)

    for (const { theme, color } of [themes[1]!, themes[0]!]) {
      window.dispatchEvent(new MessageEvent('message', {
        source: window.parent,
        data: { type: THEME_MESSAGE_TYPE, theme },
      }))
      await wrapper.vm.$nextTick()

      expect(document.documentElement.dataset.theme).toBe(theme)
      const updatedCharts = wrapper.findAllComponents(ApexStub)
      for (const [index, chart] of updatedCharts.entries()) {
        expect(chart.vm).toBe(mountedCharts[index]!.vm)
        const options = chart.props('options') as ChartOptions
        expect(options.chart.foreColor).toBe(color)
        expect(options.tooltip.theme).toBe(theme)
      }
    }
  })
})
