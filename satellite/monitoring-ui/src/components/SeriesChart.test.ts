import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import SeriesChart from './SeriesChart.vue'
import type { Series } from '@/api/types'

/** Captures what the chart library is actually asked to draw. */
const ApexStub = {
  name: 'apexchart',
  props: ['type', 'height', 'options', 'series'],
  template: '<div class="apex" />',
}

function series(values: (number | null)[]): Series {
  return {
    key: 'error_rate',
    label: 'Error rate',
    points: values.map((value, index) => ({
      t: new Date(Date.UTC(2026, 7, 24, 12, index)).toISOString(),
      value,
    })),
  }
}

function draw(points: (number | null)[], height?: number) {
  const wrapper = mount(SeriesChart, {
    props: { series: series(points), ...(height ? { height } : {}) },
    global: { stubs: { apexchart: ApexStub } },
  })
  const options = wrapper.findComponent(ApexStub).props('options') as {
    stroke: { width: number }
    markers: { size: number }
  }
  return { stroke: options.stroke.width, marker: options.markers.size }
}

const CARD = undefined // the default height a chart gets inside its card
const FULLSCREEN = 900

describe('SeriesChart height', () => {
  it('uses the common height by default and accepts the full-screen height', async () => {
    const wrapper = mount(SeriesChart, {
      props: { series: series([0.01, 0.02]) },
      global: { stubs: { apexchart: ApexStub } },
    })

    expect(wrapper.getComponent(ApexStub).props('height')).toBe(220)
    await wrapper.setProps({ height: FULLSCREEN })
    expect(wrapper.getComponent(ApexStub).props('height')).toBe(FULLSCREEN)
  })
})

describe('SeriesChart marks', () => {
  it('marks a measurement that has no neighbour to draw a line to', () => {
    // isolated buckets between empty ones need markers or the chart looks empty
    const bursty = [0.01, null, null, 0.02, null, null, 0.03, null, null, 0.04, null]

    expect(draw(bursty, CARD).marker).toBeGreaterThan(0)
  })

  it('leaves a continuous series unmarked — the line already shows every point', () => {
    const continuous = [0.01, 0.02, 0.03, 0.04, 0.05, 0.06]

    expect(draw(continuous, CARD).marker).toBe(0)
  })

  it('still marks a series of two or three points, connected or not', () => {
    expect(draw([0.01, 0.02, null, null], CARD).marker).toBeGreaterThan(0)
  })

  it('draws nothing for a window with no measurements at all', () => {
    expect(draw([null, null, null], CARD).marker).toBe(0)
  })

  it('grows the dots with the canvas and leaves the line alone', () => {
    const card = draw([0.01, null, null, 0.02, null], CARD)
    const stage = draw([0.01, null, null, 0.02, null], FULLSCREEN)

    expect(stage.marker).toBeGreaterThan(card.marker)
    expect(stage.stroke).toBe(card.stroke)
  })

  it('caps the dot so it marks a value instead of covering it', () => {
    const tall = draw([0.01, null, null, 0.02, null], 900)
    const absurd = draw([0.01, null, null, 0.02, null], 4000)

    expect(absurd.marker).toBe(tall.marker)
  })
})
