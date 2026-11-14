import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import DistributionChart from './feature-drift/DistributionChart.vue'
import ClassShareChart from './output-drift/ClassShareChart.vue'
import type { Series } from '@/api/types'

const ApexStub = {
  name: 'apexchart',
  props: ['type', 'height', 'options', 'series'],
  template: '<div />',
}
const global = { stubs: { apexchart: ApexStub } }
const label = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ01234567'
const series: Series = {
  key: 'class',
  label,
  points: [{ t: '2026-08-18T14:00:00Z', value: 0.5 }],
}

describe('chart label truncation', () => {
  it.each([220, 650])('shortens category labels at height %i and keeps full tooltip titles', async (height) => {
    const wrapper = mount(DistributionChart, {
      props: {
        height,
        distribution: {
          kind: 'categorical',
          bins: [{ label, current: 0.5 }, { label: '3', current: 0.5 }],
        },
      },
      global,
    })
    const chart = wrapper.getComponent(ApexStub)
    let options = chart.props('options')
    expect(options.xaxis.labels.formatter(label)).toBe('abcdefghijklmno…')
    expect(options.xaxis.labels.formatter('3')).toBe('3')
    expect(options.xaxis.labels.hideOverlappingLabels).toBe(true)
    expect(options.xaxis.categories).toEqual([label, '3'])
    expect(options.tooltip.x.formatter(label)).toBe(label)
    expect(chart.props('series')[1].data).toEqual([0.5, 0.5])

    await wrapper.setProps({
      distribution: { kind: 'categorical', bins: [{ label: '<&'.repeat(20), current: 1 }] },
    })
    options = chart.props('options')
    expect(options.xaxis.labels.formatter('<&'.repeat(20))).toBe('<&<&<&<&<&<&<&<…')
    expect(options.tooltip.x.formatter('<&'.repeat(20))).toBe('&lt;&amp;'.repeat(20))
    wrapper.unmount()
  })

  it.each([220, 650])('shortens raw class names before escaping at height %i and keeps full series names', async (height) => {
    const wrapper = mount(ClassShareChart, {
      props: { height, series: [series, { ...series, key: 'short', label: 'A & B' }] },
      global,
    })
    const chart = wrapper.getComponent(ApexStub)
    let options = chart.props('options')
    let w = { config: { series: chart.props('series') } }
    expect(options.legend.formatter(label, { seriesIndex: 0, w })).toBe('abcdefghijklmno…')
    expect(options.legend.formatter('A &amp; B', { seriesIndex: 1, w })).toBe('A &amp; B')
    expect(chart.props('series')[0].name).toBe(label)
    expect(chart.props('series')[0].data[0].y).toBe(0.5)

    await wrapper.setProps({ series: [{ ...series, label: '&'.repeat(20) }] })
    options = chart.props('options')
    w = { config: { series: chart.props('series') } }
    expect(options.legend.formatter('&amp;'.repeat(20), { seriesIndex: 0, w })).toBe('&amp;'.repeat(15) + '…')
    expect(chart.props('series')[0].name).toBe('&amp;'.repeat(20))
    expect(series.label).toBe(label)
    wrapper.unmount()
  })

  it('preserves numeric bin range formatting', () => {
    const wrapper = mount(DistributionChart, {
      props: {
        distribution: { kind: 'numeric', bins: [{ label: '1.234567–1.23456789e+06' }] },
      },
      global,
    })
    const options = wrapper.getComponent(ApexStub).props('options')
    expect(options.xaxis.labels.formatter(options.xaxis.categories[0])).toBe('1.235–1,234,567.89')
    wrapper.unmount()
  })
})
