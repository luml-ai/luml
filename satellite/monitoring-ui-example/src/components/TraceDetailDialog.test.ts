import { describe, expect, it } from 'vitest'
import { mount } from '@vue/test-utils'
import TraceDetailDialog from './TraceDetailDialog.vue'
import type { TraceDetail } from '@/api/types'

function makeTrace(overrides: Partial<TraceDetail> = {}): TraceDetail {
  return {
    event_id: 'event-1',
    ts: '2026-07-07T12:00:00Z',
    latency_ms: 12,
    status: 'error',
    status_code: 422,
    spans: [],
    ...overrides,
  }
}

describe('TraceDetailDialog', () => {
  it.each([
    [422, 'warn'],
    [504, 'err'],
    [200, 'ok'],
  ])('shows the HTTP status code %s next to the outcome', (code, severity) => {
    const wrapper = mount(TraceDetailDialog, {
      props: { eventId: 'event-1', trace: makeTrace({ status_code: code }), status: 'ready' },
    })

    const http = wrapper.get('[data-testid="trace-detail-http-status"]')
    expect(http.text()).toBe(String(code))
    expect(http.classes()).toContain(severity)
    expect(wrapper.text()).toContain('HTTP')
  })

  it('hides the HTTP fact while the trace is still loading', () => {
    const wrapper = mount(TraceDetailDialog, {
      props: { eventId: 'event-1', trace: null, status: 'loading' },
    })

    expect(wrapper.find('[data-testid="trace-detail-http-status"]').exists()).toBe(false)
  })
})
