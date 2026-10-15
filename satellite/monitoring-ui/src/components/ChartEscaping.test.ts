import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import ClassShareChart from './output-drift/ClassShareChart.vue'
import DistributionChart from './feature-drift/DistributionChart.vue'
import SeriesChart from './SeriesChart.vue'
import type { Series } from '@/api/types'

const ApexStub = {
  name: 'apexchart',
  props: ['type', 'height', 'options', 'series'],
  template: '<div />',
}
const global = { stubs: { apexchart: ApexStub } }
const payload = '<img src=x onerror="window.__pwned=1"> &lt;svg&gt;'
const escaped = '&lt;img src=x onerror=&quot;window.__pwned=1&quot;&gt; &amp;lt;svg&amp;gt;'
const series: Series = {
  key: 'class',
  label: payload,
  points: [{ t: '2026-08-18T14:00:00Z', value: 0.5 }],
}

describe('chart label escaping', () => {
  it('escapes class names before they reach legends and tooltips, including refreshes', async () => {
    const wrapper = mount(ClassShareChart, { props: { series: [series] }, global })
    const chart = wrapper.getComponent(ApexStub)
    expect(chart.props('series')[0].name).toBe(escaped)
    await wrapper.setProps({ series: [{ ...series, label: 'A & B' }] })
    expect(chart.props('series')[0].name).toBe('A &amp; B')
    expect(series.label).toBe(payload)
  })

  it('escapes other API-provided series names', () => {
    const wrapper = mount(SeriesChart, { props: { series }, global })
    expect(wrapper.getComponent(ApexStub).props('series')[0].name).toBe(escaped)
  })

  it.each(['categorical', 'numeric'])(
    'escapes %s tooltip titles and preserves SVG text',
    (kind) => {
      const wrapper = mount(DistributionChart, {
        props: { distribution: { kind, bins: [{ label: payload, reference: 0.5, current: 0.5 }] } },
        global,
      })
      const options = wrapper.getComponent(ApexStub).props('options')
      expect(options.xaxis.categories).toEqual([payload])
      const title = document.createElement('div')
      expect(options.tooltip.x.formatter(payload)).toBe(escaped)
      title.innerHTML = options.tooltip.x.formatter(payload)
      expect(title.textContent).toBe(payload)
      expect(title.childElementCount).toBe(0)
    },
  )
})
