import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, mount } from '@vue/test-utils'
import PrimeVue from 'primevue/config'
import type { TraceSpan as TraceSpanType } from '@/interfaces/interfaces'
import TraceSpans from '../TraceSpans.vue'
import TraceSpan from '../TraceSpan.vue'
import TraceItemsHeader from '../TraceItemsHeader.vue'
import { mockVirtualLayout } from '@/components/ui/__tests__/virtualLayout'
import { makeSpan, wideTree } from './spanFactory'

// About ten 67px rows in view.
const VIEWPORT = 670

enableAutoUnmount(afterEach)

beforeEach(() => {
  mockVirtualLayout(VIEWPORT)
})

afterEach(() => {
  vi.restoreAllMocks()
})

function mountTree(tree: TraceSpanType[], selectedSpanId?: string) {
  return mount(TraceSpans, {
    props: { tree, selectedSpanId, count: 0, maxSpanTime: 1000, minSpanTime: 0 },
    global: { plugins: [[PrimeVue, { unstyled: true }]], stubs: { AnnotationsTag: true } },
  })
}

function renderedIds(wrapper: ReturnType<typeof mountTree>) {
  return wrapper.findAllComponents(TraceSpan).map((row) => row.props('data').span_id)
}

function smallTree() {
  const root = makeSpan('root')
  const a = makeSpan('a', { parent_span_id: 'root' })
  a.children = [makeSpan('a1', { parent_span_id: 'a' }), makeSpan('a2', { parent_span_id: 'a' })]
  root.children = [a, makeSpan('b', { parent_span_id: 'root' })]
  return [root]
}

describe('TraceSpans', () => {
  it('renders only the rows in view for a 10,000-span trace', async () => {
    const wrapper = mountTree(wideTree(99, 100))
    await wrapper.vm.$nextTick()

    const rows = wrapper.findAllComponents(TraceSpan)
    expect(rows.length).toBeGreaterThan(0)
    expect(rows.length).toBeLessThan(50)
    expect(renderedIds(wrapper).slice(0, 3)).toEqual(['root', 'g0', 'g0-0'])
  })

  it('indents rows by depth', async () => {
    const wrapper = mountTree(smallTree())
    await wrapper.vm.$nextTick()

    const nesting = wrapper.findAllComponents(TraceSpan).map((row) => row.props('nesting'))
    expect(nesting).toEqual([0, 1, 2, 2, 1])
  })

  it('collapses and opens a span', async () => {
    const wrapper = mountTree(smallTree())
    await wrapper.vm.$nextTick()

    await wrapper.findAllComponents(TraceSpan)[1]!.get('button').trigger('click')
    expect(renderedIds(wrapper)).toEqual(['root', 'a', 'b'])
    expect(wrapper.findAllComponents(TraceSpan)[1]!.props('opened')).toBe(false)

    await wrapper.findAllComponents(TraceSpan)[1]!.get('button').trigger('click')
    expect(renderedIds(wrapper)).toEqual(['root', 'a', 'a1', 'a2', 'b'])
  })

  // Rows reused for another span would animate their bar and selection from the old span.
  it('replaces the row element when another span moves into it', async () => {
    const wrapper = mountTree(smallTree())
    await wrapper.vm.$nextTick()
    const rowsBefore = wrapper.findAll('.row').map((row) => row.element)

    await wrapper.findAllComponents(TraceSpan)[1]!.get('button').trigger('click')
    const rowsAfter = wrapper.findAll('.row').map((row) => row.element)

    expect(renderedIds(wrapper)).toEqual(['root', 'a', 'b'])
    expect(rowsAfter[0]).toBe(rowsBefore[0])
    expect(rowsAfter[1]).toBe(rowsBefore[1])
    expect(rowsAfter[2]).not.toBe(rowsBefore[2])
  })

  it('collapses all spans from the header and opens a whole subtree again', async () => {
    const wrapper = mountTree(smallTree())
    await wrapper.vm.$nextTick()

    await wrapper.findComponent(TraceItemsHeader).get('button').trigger('click')
    expect(renderedIds(wrapper)).toEqual(['root'])

    await wrapper.findAllComponents(TraceSpan)[0]!.get('button').trigger('click')
    expect(renderedIds(wrapper)).toEqual(['root', 'a', 'a1', 'a2', 'b'])
  })

  it('emits the clicked span and marks the selected one', async () => {
    const wrapper = mountTree(smallTree(), 'a1')
    await wrapper.vm.$nextTick()

    await wrapper.findAllComponents(TraceSpan)[1]!.trigger('click')
    expect(wrapper.emitted('select')?.[0]?.[0]).toMatchObject({ span_id: 'a' })
    const selected = wrapper.findAll('.item.selected')
    expect(selected).toHaveLength(1)
    expect(selected[0]!.text()).toContain('a1')
  })
})
