import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises, mount, type VueWrapper } from '@vue/test-utils'
import type { Series } from '@/api/monitoring/interfaces'
import MSeriesChart from '@/components/MSeriesChart.vue'
import MMultiSeriesChart from '@/components/MMultiSeriesChart.vue'

const payload = '<mark>a</mark>'
const updated = '<mark>b</mark>'

const points = [
  { t: '2026-11-20T10:00:00Z', value: 0.4 },
  { t: '2026-11-20T11:00:00Z', value: 0.5 },
  { t: '2026-11-20T12:00:00Z', value: 0.3 },
]

const series = (label: string, key = 'error_rate'): Series => ({
  key,
  label,
  unit: 'ratio',
  points,
  baseline: points,
})

const injected = (wrapper: VueWrapper) => wrapper.element.querySelectorAll('mark').length

const legendText = (wrapper: VueWrapper) =>
  wrapper.findAll('.apexcharts-legend-text').map((item) => item.text())

describe('chart label rendering', () => {
  const mounted: VueWrapper[] = []

  beforeEach(() => {
    vi.stubGlobal(
      'ResizeObserver',
      class {
        observe() {}
        unobserve() {}
        disconnect() {}
      },
    )
  })

  afterEach(() => {
    mounted.splice(0).forEach((wrapper) => wrapper.unmount())
    vi.unstubAllGlobals()
  })

  const render = async <T>(component: T, props: Record<string, unknown>) => {
    const wrapper = mount(component as never, { props, attachTo: document.body }) as VueWrapper
    mounted.push(wrapper)
    await flushPromises()
    await vi.waitFor(() => expect(wrapper.find('.apexcharts-canvas').exists()).toBe(true))
    return wrapper
  }

  const expectInert = (wrapper: VueWrapper, label: string) => {
    expect(injected(wrapper)).toBe(0)
    const legend = legendText(wrapper)
    if (legend.length) expect(legend).toContain(label)
  }

  it('keeps a single-series label literal on first render and after an update', async () => {
    const wrapper = await render(MSeriesChart, { series: series(payload) })
    expectInert(wrapper, payload)

    await wrapper.setProps({ series: series(updated) })
    await flushPromises()
    expectInert(wrapper, updated)
  })

  it('keeps multi-series labels literal on first render and after an update', async () => {
    const wrapper = await render(MMultiSeriesChart, {
      series: [series(payload, 'a'), series('plain', 'b')],
    })
    expectInert(wrapper, payload)

    await wrapper.setProps({ series: [series(updated, 'a'), series('plain', 'b')] })
    await flushPromises()
    expectInert(wrapper, updated)
  })
})
