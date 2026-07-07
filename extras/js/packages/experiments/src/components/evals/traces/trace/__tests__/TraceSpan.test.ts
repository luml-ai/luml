import { describe, it, expect } from 'vitest'
import { mount, type VueWrapper } from '@vue/test-utils'
import TraceSpan from '../TraceSpan.vue'
import type { TraceSpan as TraceSpanType } from '@/interfaces/interfaces'

// Exposes the ProgressBar fill percentage (endProgress) as a readable attribute.
const ProgressBarStub = {
  props: ['value'],
  template: '<div class="pb-stub" :data-value="value"></div>',
}

function makeSpan(start: number, end: number): TraceSpanType {
  return {
    trace_id: 't1',
    span_id: 's1',
    parent_span_id: null,
    name: 'span',
    kind: 0,
    start_time_unix_nano: start,
    end_time_unix_nano: end,
    status_code: null,
    status_message: null,
    attributes: '{}',
    events: null,
    links: null,
    children: [],
    dfs_span_type: null,
    annotation_count: null,
  }
}

function mountSpan(data: TraceSpanType, minSpanTime: number | null, maxSpanTime: number | null) {
  return mount(TraceSpan, {
    props: {
      data,
      nesting: 0,
      selectedSpanId: undefined,
      allOpened: true,
      minSpanTime,
      maxSpanTime,
    },
    global: { stubs: { ProgressBar: ProgressBarStub, AnnotationsTag: true } },
  })
}

// startProgress drives the plug width (the bar's left offset); endProgress drives the fill.
function offsetStyle(wrapper: VueWrapper): string {
  return wrapper.get('.progress-plug').attributes('style') ?? ''
}

function fillValue(wrapper: VueWrapper): string {
  return wrapper.get('.pb-stub').attributes('data-value') ?? ''
}

describe('TraceSpan waterfall geometry', () => {
  it('places a span at its real offset and width within the trace range', () => {
    const wrapper = mountSpan(makeSpan(1500, 2500), 1000, 3000)

    expect(offsetStyle(wrapper)).toContain('width: 25%')
    expect(fillValue(wrapper)).toBe('75')
  })

  it('treats a trace minimum of 0 as a real boundary, not a missing value', () => {
    const wrapper = mountSpan(makeSpan(50, 150), 0, 200)

    // Old falsy guard (`!minSpanTime`) short-circuited a 0 minimum to a 0 offset.
    expect(offsetStyle(wrapper)).toContain('width: 25%')
    expect(fillValue(wrapper)).toBe('75')
  })

  it('renders a zero-range trace at zero offset and full width without NaN', () => {
    const wrapper = mountSpan(makeSpan(1000, 1000), 1000, 1000)

    expect(offsetStyle(wrapper)).toContain('width: 0%')
    expect(fillValue(wrapper)).toBe('100')
    expect(wrapper.html()).not.toContain('NaN')
  })

  it('clamps offsets that fall outside the trace range to 0–100', () => {
    const wrapper = mountSpan(makeSpan(500, 3000), 1000, 2000)

    expect(offsetStyle(wrapper)).toContain('width: 0%')
    expect(fillValue(wrapper)).toBe('100')
  })

  it('falls back to zero offset / full width when min or max is absent', () => {
    const wrapper = mountSpan(makeSpan(1000, 2000), null, null)

    expect(offsetStyle(wrapper)).toContain('width: 0%')
    expect(fillValue(wrapper)).toBe('100')
    expect(wrapper.html()).not.toContain('NaN')
  })
})
