import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TracesTab from './TracesTab.vue'
import { SectionState, type TraceDetail, type TracesResponse } from '@/api/types'
import type { LoadStatus } from '@/composables/useMonitoringDashboard'
import { makeTraceDetail, makeTraces } from '@/test/fixtures'

function mountTab(
  props: {
    traces?: TracesResponse | null
    status?: LoadStatus
    openTraceId?: string | null
    traceDetail?: TraceDetail | null
    traceDetailStatus?: LoadStatus
  } = {},
) {
  return mount(TracesTab, {
    props: {
      traces: makeTraces(),
      status: 'ready',
      openTraceId: null,
      traceDetail: null,
      traceDetailStatus: 'idle',
      ...props,
    },
    global: { stubs: { apexchart: true } },
  })
}

describe('TracesTab', () => {
  it('renders the local Traces panel with recent inference calls', () => {
    const wrapper = mountTab()

    expect(wrapper.find('[data-testid="traces-panel"]').exists()).toBe(true)
    expect(wrapper.findAll('[data-testid="trace-row"]')).toHaveLength(2)
  })

  it('emits a page request when paging', async () => {
    const wrapper = mountTab({ traces: makeTraces({ total: 60, offset: 0, limit: 20 }) })

    await wrapper.find('[data-testid="traces-next"]').trigger('click')

    expect(wrapper.emitted('page')?.[0]).toEqual([20])
  })

  it('shows the empty state when there are no inference calls', () => {
    const wrapper = mountTab({
      traces: makeTraces({ state: SectionState.EMPTY, rows: [], total: 0 }),
    })

    expect(wrapper.find('[data-testid="traces-panel"] [data-testid="state-empty"]').exists()).toBe(
      true,
    )
  })

  it('emits open with the clicked call id', async () => {
    const wrapper = mountTab()

    await wrapper.findAll('[data-testid="trace-row"]')[0].trigger('click')

    expect(wrapper.emitted('open')?.[0]).toEqual([makeTraces().rows[0].event_id])
  })

  it('copies a call id from the table without opening the call', async () => {
    const wrapper = mountTab()

    const row = wrapper.findAll('[data-testid="trace-row"]')[0]
    const copy = row.find('[data-testid="copy-button"]')
    expect(copy.attributes('aria-label')).toBe('Copy event id')

    await copy.trigger('click')

    expect(wrapper.emitted('open')).toBeUndefined()
  })

  it('renders no detail dialog until a trace is opened', () => {
    const wrapper = mountTab()

    expect(wrapper.find('[data-testid="trace-detail-dialog"]').exists()).toBe(false)
  })

  it('renders the span tree of the opened call, root first', () => {
    const wrapper = mountTab({
      openTraceId: 'evt-1',
      traceDetail: makeTraceDetail(),
      traceDetailStatus: 'ready',
    })

    const spans = wrapper.findAll('[data-testid="trace-span-item"]')
    expect(spans).toHaveLength(2)
    expect(spans[0].text()).toContain('inference')
    expect(spans[1].text()).toContain('model.execute')
    expect(spans[1].text()).toContain('1ms') // child duration, formatted like the Platform
  })

  it('shows the root span attributes — the full payloads — in the details panel', () => {
    const wrapper = mountTab({
      openTraceId: 'evt-1',
      traceDetail: makeTraceDetail(),
      traceDetailStatus: 'ready',
    })

    const body = wrapper.find('[data-testid="trace-span-body"]')
    expect(body.text()).toContain('6.82')
    expect(body.text()).toContain('Virginica')
  })

  it('selects a child span and shows its own details', async () => {
    const wrapper = mountTab({
      openTraceId: 'evt-1',
      traceDetail: makeTraceDetail(),
      traceDetailStatus: 'ready',
    })

    await wrapper.findAll('[data-testid="trace-span-item"]')[1].trigger('click')

    const body = wrapper.find('[data-testid="trace-span-body"]')
    expect(body.text()).toContain('model.execute')
    expect(body.text()).not.toContain('Virginica') // payloads live on the root span
  })

  it('exposes span metadata on the Metadata tab', async () => {
    const wrapper = mountTab({
      openTraceId: 'evt-1',
      traceDetail: makeTraceDetail(),
      traceDetailStatus: 'ready',
    })

    await wrapper.find('[data-testid="trace-tab-metadata"]').trigger('click')

    expect(wrapper.find('[data-testid="trace-span-body"]').text()).toContain('trc-1')
  })

  it('emits close-trace from the dialog close button', async () => {
    const wrapper = mountTab({
      openTraceId: 'evt-1',
      traceDetail: null,
      traceDetailStatus: 'loading',
    })

    await wrapper.find('[data-testid="trace-detail-close"]').trigger('click')

    expect(wrapper.emitted('close-trace')).toHaveLength(1)
  })
})
