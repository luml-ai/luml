import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TraceSpanBody from './TraceSpanBody.vue'
import { makeTraceDetail } from '@/test/fixtures'
import { buildSpanTree } from '@/lib/spans'

function mountBody() {
  const tree = buildSpanTree(makeTraceDetail().spans)
  return mount(TraceSpanBody, {
    props: { data: tree[0] },
    // the full-screen viewer teleports to the body; keep it inline for the assertions
    global: { stubs: { teleport: true } },
  })
}

describe('TraceSpanBody', () => {
  it('offers copy and full screen on every attribute', () => {
    const wrapper = mountBody()

    const fields = wrapper.findAll('[data-testid="span-field"]')
    expect(fields.map((f) => f.find('.key').text())).toEqual([
      'inference.inputs',
      'inference.output',
    ])
    for (const field of fields) {
      expect(field.find('[data-testid="copy-button"]').exists()).toBe(true)
      expect(field.find('[data-testid="span-field-expand"]').exists()).toBe(true)
    }
  })

  it('opens the payload full screen and closes it again', async () => {
    const wrapper = mountBody()
    expect(wrapper.find('[data-testid="field-fullscreen"]').exists()).toBe(false)

    await wrapper.findAll('[data-testid="span-field-expand"]')[1].trigger('click')

    const viewer = wrapper.find('[data-testid="field-fullscreen"]')
    expect(viewer.text()).toContain('inference.output')
    expect(viewer.text()).toContain('Virginica') // the whole value, not the clipped preview
    expect(viewer.find('[data-testid="copy-button"]').exists()).toBe(true)
    expect(document.body.style.overflow).toBe('hidden')

    await viewer.find('[data-testid="field-fullscreen-close"]').trigger('click')
    expect(wrapper.find('[data-testid="field-fullscreen"]').exists()).toBe(false)
    expect(document.body.style.overflow).toBe('')
  })

  it('gives the metadata ids the same copy affordance', async () => {
    const wrapper = mountBody()

    await wrapper.find('[data-testid="trace-tab-metadata"]').trigger('click')

    const fields = wrapper.findAll('[data-testid="span-field"]')
    const keys = fields.map((f) => f.find('.key').text())
    expect(keys).toContain('span_id')
    expect(keys).toContain('trace_id')
    expect(fields.every((f) => f.find('[data-testid="copy-button"]').exists())).toBe(true)
  })
})
