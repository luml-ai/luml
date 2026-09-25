import { h, nextTick, type VNode } from 'vue'
import { mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import { VueFlow, type VueFlowStore } from '@vue-flow/core'

import FlowCanvas from '@/flow/workbench/components/canvas/FlowCanvas.vue'
import { mainCells } from '@/flow/workbench/fixtures'
import NotebookColumn from '@/flow/workbench/pages/NotebookColumn.vue'
import type { FlowCell } from '@/flow/workbench/model/types'

const props = {
  cells: mainCells,
  branch: 'main',
  selectedSlug: 'features',
  tintedSlugs: new Set<string>(),
  preflights: {},
}

function cardSlot({ cell }: { cell: FlowCell }): VNode {
  return h('button', { class: `control-${cell.slug}` }, cell.slug)
}

describe('card selection keeps the current viewport still', () => {
  it('does not scroll the notebook when the selection came from a card control', async () => {
    const scrollIntoView = vi
      .spyOn(Element.prototype, 'scrollIntoView')
      .mockImplementation(() => {})
    const wrapper = mount(NotebookColumn, { props, slots: { card: cardSlot } })
    await nextTick()
    scrollIntoView.mockClear()

    await wrapper.get('.control-train_model').trigger('pointerdown')
    await wrapper.setProps({ selectedSlug: 'train_model' })
    await nextTick()

    expect(scrollIntoView).not.toHaveBeenCalled()
    expect(wrapper.emitted('select')).toEqual([['train_model']])

    await wrapper.get('.control-train_model').trigger('pointerdown')
    expect(wrapper.emitted('select')).toEqual([['train_model']])
    scrollIntoView.mockRestore()
    wrapper.unmount()
  })

  it('does not pan the canvas when the selection came from a card control', async () => {
    const wrapper = mount(FlowCanvas, { props, slots: { card: cardSlot } })
    const fitView = vi.fn().mockResolvedValue(true)
    wrapper.findComponent(VueFlow).vm.$emit('paneReady', {
      fitView,
      getViewport: () => ({ x: 0, y: 0, zoom: 1 }),
    } as unknown as VueFlowStore)
    await nextTick()
    fitView.mockClear()

    await wrapper.get('.control-train_model').trigger('pointerdown')
    await wrapper.setProps({ selectedSlug: 'train_model' })
    await nextTick()

    expect(fitView).not.toHaveBeenCalled()
    expect(wrapper.emitted('select')).toEqual([['train_model']])

    await wrapper.get('.control-train_model').trigger('pointerdown')
    expect(wrapper.emitted('select')).toEqual([['train_model']])
    wrapper.unmount()
  })
})
