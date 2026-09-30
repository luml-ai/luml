import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SeriesChart from './SeriesChart.vue'
import PredictionTrendChart from './output-drift/PredictionTrendChart.vue'
import ClassShareChart from './output-drift/ClassShareChart.vue'
import DistributionChart from './feature-drift/DistributionChart.vue'
import PcaScatter from './feature-drift/PcaScatter.vue'
import ReferenceProfilePanel from './feature-drift/ReferenceProfilePanel.vue'
import TopDriftedList from './overview/TopDriftedList.vue'
import type { FeatureDistribution, Series } from '@/api/types'
import { Severity } from '@/api/types'
import { makeReferenceProfile } from '@/test/fixtures'

const ApexStub = {
  name: 'apexchart',
  props: ['type', 'height', 'options', 'series'],
  template: '<div />',
}
const global = { stubs: { apexchart: ApexStub } }
const series: Series = {
  key: 'prediction_mean',
  label: 'Mean',
  points: [{ t: '2026-08-18T14:00:00Z', value: 1.23456 }],
  baseline: [{ t: '2026-08-18T14:00:00Z', value: 0.0004 }],
}
type Options = {
  xaxis: { categories: string[] }
  yaxis: { labels: { formatter: (value: number | null) => string } }
  tooltip: { y: { formatter: (value: number | null) => string } }
}

describe('monitoring chart number formatting', () => {
  it('trims PSI values next to the overview bars', () => {
    const wrapper = mount(TopDriftedList, {
      props: { features: [{ feature: 'income', psi: 0.300001, severity: Severity.OK }] },
    })
    expect(wrapper.get('.psi').text()).toBe('PSI 0.3')
  })

  it('formats reference histogram edges and category bar percentages', async () => {
    const wrapper = mount(ReferenceProfilePanel, {
      props: {
        status: 'ready',
        profile: makeReferenceProfile({
          feature: {
            feature: 'income',
            kind: 'numeric',
            summary: {},
            bin_edges: [0.0004, 0.5, 1.234567],
          },
        }),
      },
    })
    expect(wrapper.get('.edge-values').text()).toBe('0  ·  0.5  ·  1.235')
    await wrapper.setProps({
      profile: makeReferenceProfile({
        feature: {
          feature: 'region',
          kind: 'categorical',
          summary: {},
          categories: ['north', 'south'],
          category_probabilities: [0.5, 0.12345678],
        },
      }),
    })
    expect(wrapper.findAll('.cat-prob').map((label) => label.text())).toEqual(['50%', '12.346%'])
  })

  it('uses the same precision for time-series axes and tooltips without rounding the data', () => {
    const wrapper = mount(SeriesChart, { props: { series }, global })
    const chart = wrapper.getComponent(ApexStub)
    const options = chart.props('options') as Options
    expect(options.yaxis.labels.formatter(1.23456)).toBe('1.235')
    expect(options.tooltip.y.formatter(-0.0004)).toBe('0')
    expect(options.tooltip.y.formatter(null)).toBe('—')
    expect(chart.props('series')[0].data[0][1]).toBe(1.23456)
    expect(chart.props('series')[1].data[0][1]).toBe(0.0004)
  })

  it('uses percentages on time-series axes and tooltips', () => {
    const wrapper = mount(SeriesChart, { props: { series: { ...series, unit: 'ratio' } }, global })
    const options = wrapper.getComponent(ApexStub).props('options') as Options
    expect(options.yaxis.labels.formatter(0.12345678)).toBe('12.346%')
    expect(options.tooltip.y.formatter(0.005)).toBe('0.5%')
  })

  it('formats prediction band edges and compact values like its axis', () => {
    const wrapper = mount(PredictionTrendChart, {
      props: {
        trend: [series, { ...series, key: 'prediction_p05' }, { ...series, key: 'prediction_p95' }],
      },
      global,
    })
    const options = wrapper.getComponent(ApexStub).props('options') as Options
    expect(options.yaxis.labels.formatter(1234567.89)).toBe('1.235M')
    expect(options.tooltip.y.formatter(0.5)).toBe('0.5')
    expect(options.tooltip.y.formatter(1.23456)).toBe('1.235')
    expect(options.tooltip.y.formatter(null)).toBe('—')
  })

  it('formats class shares consistently on its axis and in its tooltip', () => {
    const wrapper = mount(ClassShareChart, { props: { series: [series] }, global })
    const options = wrapper.getComponent(ApexStub).props('options') as Options
    expect(options.yaxis.labels.formatter(0.12345678)).toBe('12.346%')
    expect(options.tooltip.y.formatter(0.5)).toBe('50%')
    expect(options.tooltip.y.formatter(null)).toBe('—')
  })

  it('rounds numeric distribution bin edges, including negative and scientific values', () => {
    const distribution: FeatureDistribution = {
      kind: 'numeric',
      bins: [
        { label: '-1.234567–0.0004', reference: 0.12345678 },
        { label: '0.0004–1.234567', current: 0.5 },
        { label: '1.234567–1.23456789e+06', current: 0.5 },
      ],
    }
    const wrapper = mount(DistributionChart, { props: { distribution }, global })
    const options = wrapper.getComponent(ApexStub).props('options') as Options
    expect(options.xaxis.categories).toEqual(['-1.235–0', '0–1.235', '1.235–1,234,567.89'])
    expect(options.yaxis.labels.formatter(0.12345678)).toBe('12.346%')
    expect(options.tooltip.y.formatter(0.5)).toBe('50%')
    expect(options.tooltip.y.formatter(null)).toBe('—')
    expect(distribution.bins[0].label).toBe('-1.234567–0.0004')
  })

  it('preserves numeric-looking categorical names and unknown numeric labels', () => {
    for (const kind of ['categorical', 'numeric']) {
      const label = kind === 'categorical' ? '1.234567–2.345678' : 'unknown'
      const wrapper = mount(DistributionChart, {
        props: { distribution: { kind, bins: [{ label }] } },
        global,
      })
      const options = wrapper.getComponent(ApexStub).props('options') as Options
      expect(options.xaxis.categories).toEqual([label])
    }
  })

  it('uses trimmed numbers on both PCA axes', () => {
    const wrapper = mount(PcaScatter, { props: { reference: [], current: [] } })
    expect(wrapper.findAll('text.tick').map((tick) => tick.text())).toEqual([
      '-1.16',
      '-0.58',
      '0',
      '0.58',
      '1.16',
      '-1.16',
      '-0.696',
      '-0.232',
      '0.232',
      '0.696',
      '1.16',
    ])
  })
})
