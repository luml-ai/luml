import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import PcaScatter from './PcaScatter.vue'
import type { PcaPoint } from '@/api/types'

function ring(cx: number, cy: number, r: number): PcaPoint[] {
  return Array.from({ length: 17 }, (_, i) => {
    const t = (2 * Math.PI * i) / 16
    return { x: cx + r * Math.cos(t), y: cy + r * Math.sin(t) }
  })
}

const CLOUD: PcaPoint[] = Array.from({ length: 50 }, (_, i) => ({
  x: (i % 10) - 5,
  y: Math.floor(i / 10) - 2,
}))

describe('PcaScatter', () => {
  it('names both clouds — the legend used to come from the charting library', () => {
    const wrapper = mount(PcaScatter, {
      props: { reference: [], current: CLOUD, referenceEllipse: ring(0, 0, 2) },
    })

    const legend = wrapper.get('[data-testid="pca-legend"]')
    expect(legend.text()).toContain('Reference (training)')
    expect(legend.text()).toContain('Logged (current window)')
    expect(legend.text()).not.toContain('Beyond range')
  })

  it('explains the pinned markers in the legend once there are any', () => {
    const wrapper = mount(PcaScatter, {
      props: {
        reference: [],
        current: [...CLOUD, { x: 4000, y: 0 }],
        referenceEllipse: ring(0, 0, 2),
      },
    })

    expect(wrapper.get('[data-testid="pca-legend"]').text()).toContain('Beyond range')
  })

  it('draws both Gaussians as ellipses', () => {
    const wrapper = mount(PcaScatter, {
      props: {
        reference: [],
        current: CLOUD,
        referenceEllipse: ring(0, 0, 2),
        currentEllipse: ring(1, 1, 3),
      },
    })

    expect(wrapper.find('[data-testid="reference-ellipse"]').exists()).toBe(true)
    expect(wrapper.find('[data-testid="current-ellipse"]').exists()).toBe(true)
  })

  it('keeps the reference visible even without a training point cloud', () => {
    const wrapper = mount(PcaScatter, {
      props: { reference: [], current: CLOUD, referenceEllipse: ring(0, 0, 2) },
    })

    // artifacts built before the profile carried sample points still get a reference shape
    expect(wrapper.find('[data-testid="reference-ellipse"]').exists()).toBe(true)
    expect(wrapper.findAll('circle.dot.reference')).toHaveLength(0)
  })

  it('pins extreme rows to the edge and says how many', () => {
    const wrapper = mount(PcaScatter, {
      props: {
        reference: [],
        current: [...CLOUD, { x: 4000, y: 0 }, { x: -4000, y: 0 }],
        referenceEllipse: ring(0, 0, 2),
      },
    })

    // without clipping two rows out of fifty-two would own the whole width
    expect(wrapper.get('[data-testid="pca-beyond-range"]').text()).toContain('2 points')
    expect(wrapper.findAll('circle.dot.clipped')).toHaveLength(2)
  })

  it('says nothing about clipping when everything fits', () => {
    const wrapper = mount(PcaScatter, {
      props: { reference: [], current: CLOUD, referenceEllipse: ring(0, 0, 6) },
    })

    expect(wrapper.find('[data-testid="pca-beyond-range"]').exists()).toBe(false)
  })
})
