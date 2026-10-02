import { afterEach, describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import ChartFrame from './ChartFrame.vue'

function mountFrame() {
  return mount(ChartFrame, {
    props: { title: 'Requests over time', subtitle: 'prediction calls per interval' },
    slots: {
      // the slot renders wherever the frame puts it, at whatever height it is given
      default: '<div class="plot" :data-height="height">chart</div>',
    },
    global: { stubs: { teleport: true } },
  })
}

describe('ChartFrame', () => {
  afterEach(() => vi.unstubAllGlobals())

  it('gives charts the common in-place height', () => {
    const wrapper = mountFrame()

    expect(wrapper.get('.plot').attributes('data-height')).toBe('220')
  })

  it('keeps the in-place height on narrow screens and enlarges the full-screen chart', async () => {
    vi.stubGlobal('innerWidth', 360)
    vi.stubGlobal('innerHeight', 400)
    const wrapper = mountFrame()

    await wrapper.get('[data-testid="chart-expand"]').trigger('click')
    expect(wrapper.findAll('.plot').map((plot) => plot.attributes('data-height'))).toEqual([
      '220', '320',
    ])

    vi.stubGlobal('innerHeight', 800)
    globalThis.dispatchEvent(new Event('resize'))
    await wrapper.vm.$nextTick()
    expect(wrapper.findAll('.plot').map((plot) => plot.attributes('data-height'))).toEqual([
      '220', '650',
    ])
    wrapper.unmount()
  })

  it('shows the chart in place with its title until asked for more room', () => {
    const wrapper = mountFrame()

    expect(wrapper.text()).toContain('Requests over time')
    expect(wrapper.text()).toContain('prediction calls per interval')
    expect(wrapper.find('[data-testid="chart-fullscreen"]').exists()).toBe(false)
  })

  it('opens full screen and closes again', async () => {
    const wrapper = mountFrame()

    await wrapper.find('[data-testid="chart-expand"]').trigger('click')
    expect(wrapper.find('[data-testid="chart-fullscreen"]').exists()).toBe(true)
    // the chart is rendered twice: in place underneath, and on the full-screen stage
    expect(wrapper.findAll('.plot')).toHaveLength(2)

    await wrapper.find('[data-testid="chart-fullscreen-close"]').trigger('click')
    expect(wrapper.find('[data-testid="chart-fullscreen"]').exists()).toBe(false)
  })

  it('gives the full-screen chart a taller height than the one in place', async () => {
    const wrapper = mountFrame()
    const inPlace = wrapper.find('.plot').attributes('data-height')

    await wrapper.find('[data-testid="chart-expand"]').trigger('click')
    const heights = wrapper.findAll('.plot').map((plot) => Number(plot.attributes('data-height')))

    expect(heights[1]).toBeGreaterThan(Number(inPlace))
  })

  it('closes on Escape without letting the key reach a drawer underneath', async () => {
    const wrapper = mountFrame()
    await wrapper.find('[data-testid="chart-expand"]').trigger('click')

    const event = new KeyboardEvent('keydown', { key: 'Escape', cancelable: true })
    const stopped = vi.spyOn(event, 'stopPropagation')
    document.dispatchEvent(event)
    await wrapper.vm.$nextTick()

    expect(stopped).toHaveBeenCalled()
    expect(wrapper.find('[data-testid="chart-fullscreen"]').exists()).toBe(false)
  })

  it('restores page scrolling when it closes', async () => {
    const wrapper = mountFrame()

    await wrapper.find('[data-testid="chart-expand"]').trigger('click')
    expect(document.body.style.overflow).toBe('hidden')

    await wrapper.find('[data-testid="chart-fullscreen-close"]').trigger('click')
    expect(document.body.style.overflow).toBe('')
  })

  it('leaves nothing behind when unmounted while open', async () => {
    const wrapper = mountFrame()
    await wrapper.find('[data-testid="chart-expand"]').trigger('click')

    wrapper.unmount()

    // a tab switched away from must not keep the page unscrollable
    expect(document.body.style.overflow).toBe('')
  })
})
