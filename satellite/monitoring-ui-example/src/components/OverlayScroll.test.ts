import { afterEach, describe, expect, it } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import DetailDrawer from './DetailDrawer.vue'
import ChartFrame from './ChartFrame.vue'
import FieldFullscreen from './trace/FieldFullscreen.vue'

enableAutoUnmount(afterEach)
afterEach(() => { document.body.style.overflow = '' })

function drawer(open = false) {
  return mount(DetailDrawer, {
    props: { open, feature: 'region', eyebrow: 'Feature', testid: 'drawer' },
    global: { stubs: { teleport: true } },
  })
}

function chart() {
  return mount(ChartFrame, { global: { stubs: { teleport: true } } })
}

describe('overlay scrolling', () => {
  it('keeps the drawer locked when a nested chart closes and restores the original overflow', async () => {
    document.body.style.overflow = 'scroll'
    const panel = drawer()
    await panel.setProps({ open: true })
    expect(document.body.style.overflow).toBe('hidden')
    const frame = chart()
    await frame.get('[data-testid="chart-expand"]').trigger('click')
    expect(document.body.style.overflow).toBe('hidden')

    await frame.get('[data-testid="chart-fullscreen-close"]').trigger('click')
    expect(document.body.style.overflow).toBe('hidden')
    frame.unmount()
    expect(document.body.style.overflow).toBe('hidden')
    await panel.setProps({ open: false })
    expect(document.body.style.overflow).toBe('scroll')
    panel.unmount()
    expect(document.body.style.overflow).toBe('scroll')
  })

  it('locks an initially open drawer and restores overflow after a field viewer unmounts', async () => {
    document.body.style.overflow = 'auto'
    const panel = drawer(true)
    expect(document.body.style.overflow).toBe('hidden')
    const field = mount(FieldFullscreen, {
      props: { name: 'input', value: 'hello' },
      global: { stubs: { teleport: true } },
    })
    field.unmount()
    expect(document.body.style.overflow).toBe('hidden')
    panel.unmount()
    expect(document.body.style.overflow).toBe('auto')
  })

  it('preserves overflow when a closed overlay unmounts', () => {
    document.body.style.overflow = 'auto'
    chart().unmount()
    drawer().unmount()
    expect(document.body.style.overflow).toBe('auto')
  })

  it('keeps scrolling locked until the last overlay closes even if its parent closes first', async () => {
    document.body.style.overflow = 'scroll'
    const panel = drawer()
    await panel.setProps({ open: true })
    const frame = chart()
    await frame.get('[data-testid="chart-expand"]').trigger('click')
    panel.unmount()
    expect(document.body.style.overflow).toBe('hidden')
    frame.unmount()
    expect(document.body.style.overflow).toBe('scroll')
  })
})
