import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'
import type { ExperimentSnapshotProvider, SpanPayload, TraceSpan } from '@/interfaces/interfaces'
import { useEvalsStore } from '@/store/evals'
import TraceBody from '../body/TraceBody.vue'
import { makeSpan } from './spanFactory'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

// TabList updates its ink bar 150 ms after mount; once unmounted, that timer finds no DOM refs and
// does nothing, so it cannot fire against a torn-down test environment.
enableAutoUnmount(afterEach)

type Deferred = {
  resolve: (payload: SpanPayload) => void
  reject: (error: Error) => void
}

function payloadFor(spanId: string): SpanPayload {
  return {
    attributes: JSON.stringify({ loaded: `value of ${spanId}` }),
    events: null,
    links: null,
    status_message: null,
  }
}

let pending: Map<string, Deferred[]>
let getSpanPayload: ReturnType<typeof vi.fn>

function setupProvider() {
  pending = new Map()
  getSpanPayload = vi.fn(
    (_modelId: string, _traceId: string, spanId: string) =>
      new Promise<SpanPayload>((resolve, reject) => {
        pending.set(spanId, [...(pending.get(spanId) ?? []), { resolve, reject }])
      }),
  )
  const provider = {
    getSpanAnnotations: vi.fn(async () => []),
    getSpanPayload,
  }
  useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
}

function structureSpan(spanId: string): TraceSpan {
  return makeSpan(spanId, { attributes: null as unknown as string, payloadLoaded: false })
}

function mountBody(data: TraceSpan) {
  return mount(TraceBody, {
    props: { data, artifactId: 'model-1', traceId: 't1' },
    global: {
      plugins: [[PrimeVue, { unstyled: true }]],
      directives: { tooltip: Tooltip },
      stubs: { AnnotationsButton: true, AnnotationsView: true },
    },
  })
}

function resolve(spanId: string) {
  pending.get(spanId)?.shift()?.resolve(payloadFor(spanId))
}

describe('TraceBody span payload', () => {
  beforeEach(() => {
    vi.stubGlobal(
      'matchMedia',
      vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
    )
    setActivePinia(createPinia())
    setupProvider()
  })

  it('does not fetch a span that already has its payload', async () => {
    const wrapper = mountBody(
      makeSpan('s1', { attributes: JSON.stringify({ model: 'gpt-4o' }), payloadLoaded: true }),
    )
    await flushPromises()

    expect(getSpanPayload).not.toHaveBeenCalled()
    expect(wrapper.text()).toContain('gpt-4o')
    expect(wrapper.text()).not.toContain('Loading span data.')
  })

  it('fetches the payload of a structure-only span and shows it', async () => {
    const wrapper = mountBody(structureSpan('s1'))
    await flushPromises()

    expect(getSpanPayload).toHaveBeenCalledExactlyOnceWith('model-1', 't1', 's1')
    expect(wrapper.text()).toContain('Loading span data.')

    resolve('s1')
    await flushPromises()

    expect(wrapper.text()).not.toContain('Loading span data.')
    expect(wrapper.text()).toContain('value of s1')
  })

  it('uses the cached payload when a span is selected again', async () => {
    const wrapper = mountBody(structureSpan('s1'))
    resolve('s1')
    await flushPromises()
    await wrapper.setProps({ data: structureSpan('s2') })
    resolve('s2')
    await flushPromises()

    await wrapper.setProps({ data: structureSpan('s1') })

    expect(wrapper.text()).toContain('value of s1')
    expect(wrapper.text()).not.toContain('Loading span data.')
    expect(getSpanPayload).toHaveBeenCalledTimes(2)
  })

  it('ignores an answer for a span that is no longer selected', async () => {
    const wrapper = mountBody(structureSpan('s1'))
    await flushPromises()
    await wrapper.setProps({ data: structureSpan('s2') })
    await flushPromises()

    resolve('s2')
    await flushPromises()
    resolve('s1')
    await flushPromises()

    expect(wrapper.text()).toContain('value of s2')
    expect(wrapper.text()).not.toContain('value of s1')
  })

  it('shows an error and fetches again when the span is selected again', async () => {
    const wrapper = mountBody(structureSpan('s1'))
    await flushPromises()
    pending.get('s1')?.shift()?.reject(new Error('read failed'))
    await flushPromises()

    expect(wrapper.text()).toContain('Cannot load span data.')
    expect(wrapper.text()).not.toContain('read failed')

    await wrapper.setProps({ data: structureSpan('s2') })
    await wrapper.setProps({ data: structureSpan('s1') })
    resolve('s1')
    await flushPromises()

    expect(getSpanPayload).toHaveBeenCalledTimes(3)
    expect(wrapper.text()).toContain('value of s1')
  })

  it('keeps an open span shown while a refresh reads its replaced payload', async () => {
    const wrapper = mountBody(structureSpan('s1'))
    resolve('s1')
    await flushPromises()

    useEvalsStore().clearSpanPayloads()
    await flushPromises()
    expect(getSpanPayload).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).toContain('value of s1')
    expect(wrapper.text()).not.toContain('Loading span data.')

    pending
      .get('s1')
      ?.shift()
      ?.resolve({ ...payloadFor('s1'), attributes: '{"loaded":"new"}' })
    await flushPromises()
    expect(wrapper.text()).toContain('new')
    expect(wrapper.text()).not.toContain('value of s1')
  })
})
