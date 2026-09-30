import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import { Granularity } from '@/api/types'
import {
  makeAlerts,
  makeDataQuality,
  makeFeatureDriftDetail,
  makeOutputDrift,
  makeOverview,
  makeRuntime,
} from '@/test/fixtures'
import OverviewTab from './overview/OverviewTab.vue'
import RuntimeTab from './runtime/RuntimeTab.vue'
import InvalidValuesPanel from './data-quality/InvalidValuesPanel.vue'
import AlertDetailPanel from './alerts/AlertDetailPanel.vue'
import FeatureDetailPanel from './feature-drift/FeatureDetailPanel.vue'
import OutputDriftTab from './output-drift/OutputDriftTab.vue'
import SeriesChart from './SeriesChart.vue'
import DistributionChart from './feature-drift/DistributionChart.vue'
import PredictionTrendChart from './output-drift/PredictionTrendChart.vue'
import ClassShareChart from './output-drift/ClassShareChart.vue'

const ApexStub = {
  name: 'apexchart',
  props: ['type', 'height', 'options', 'series'],
  template: '<div class="apex" />',
}
const global = { stubs: { apexchart: ApexStub, teleport: true } }
const output = makeOutputDrift()
const history = output.psi_over_time!
const distribution = output.distribution!

describe('monitoring chart heights', () => {
  it('uses one height across every tab, including confidence and class share charts', () => {
    const wrappers = [
      mount(OverviewTab, {
        props: { overview: makeOverview(), status: 'ready', granularity: Granularity.AUTO },
        global,
      }),
      mount(RuntimeTab, {
        props: { runtime: makeRuntime(), status: 'ready', granularity: Granularity.AUTO },
        global,
      }),
      mount(InvalidValuesPanel, {
        props: { row: makeDataQuality().features[0], trends: [history], trendsStatus: 'ready' },
        global,
      }),
      mount(AlertDetailPanel, { props: { alert: makeAlerts().groups[0].alerts[0] }, global }),
      mount(FeatureDetailPanel, { props: { detail: makeFeatureDriftDetail() }, global }),
      mount(OutputDriftTab, {
        props: {
          outputDrift: makeOutputDrift({
            top_changed: [{ label: 'class', reference: 0.5, current: 0.6, delta: 0.1 }],
            class_share_trend: [history],
            confidence: {
              psi: 0.1,
              mean: 0.9,
              low_confidence_rate: 0.1,
              low_confidence_threshold: 0.8,
              distribution,
              mean_over_time: history,
            },
          }),
          status: 'ready',
        },
        global,
      }),
    ]

    for (const wrapper of wrappers) {
      const charts = wrapper.findAllComponents(ApexStub)
      expect(charts.length).toBeGreaterThan(0)
      expect(new Set(charts.map((chart) => chart.props('height')))).toEqual(new Set([180]))
      wrapper.unmount()
    }
  })

  it.each([
    ['series', () => mount(SeriesChart, { props: { series: history }, global })],
    ['distribution', () => mount(DistributionChart, { props: { distribution }, global })],
    ['prediction', () => mount(PredictionTrendChart, { props: { trend: output.trend }, global })],
    ['class share', () => mount(ClassShareChart, { props: { series: [history] }, global })],
  ] as const)('keeps the %s plot height independent of its legend', async (_name, draw) => {
    const wrapper = draw()
    const chart = wrapper.getComponent(ApexStub)

    expect(chart.props('height')).toBe(180)
    const options = chart.props('options')
    expect(options.grid.padding.top).toBe(40)
    expect(options.legend.floating).toBe(true)
    expect(options.legend.height).toBeLessThanOrEqual(options.grid.padding.top)

    await wrapper.setProps({ height: 650 })
    expect(chart.props('height')).toBe(650)
    expect(chart.props('options').grid.padding.top).toBe(40)
    wrapper.unmount()
  })

  it('keeps empty feature and output chart slots at the common height', () => {
    const wrappers = [
      mount(FeatureDetailPanel, {
        props: { detail: makeFeatureDriftDetail({ distribution: null, psi_over_time: null }) },
        global,
      }),
      mount(OutputDriftTab, {
        props: {
          outputDrift: makeOutputDrift({ distribution: null, psi_over_time: null }),
          status: 'ready',
        },
        global,
      }),
    ]

    for (const wrapper of wrappers) {
      expect(wrapper.findAll('.plot').map((plot) => (plot.element as HTMLElement).style.minHeight))
        .toEqual(['180px', '180px'])
      wrapper.unmount()
    }
  })
})
