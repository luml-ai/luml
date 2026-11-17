import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'
import type { ExperimentSnapshotProvider, SpanPayload, TraceSpan } from '@/interfaces/interfaces'
import { useEvalsStore } from '@/store/evals'
import { mockVirtualLayout } from '@/components/ui/__tests__/virtualLayout'
import TraceDialog from '../TraceDialog.vue'
import TraceSpanRow from '../TraceSpan.vue'
import { makeSpan } from './spanFactory'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

// TabList updates its ink bar 150 ms after mount; once unmounted, that timer finds no DOM refs and
// does nothing, so it cannot fire against a torn-down test environment.
enableAutoUnmount(afterEach)

const DialogStub = {
  name: 'Dialog',
  props: ['closeOnEscape'],
  template: '<div class="dialog-stub"><slot /></div>',
}

let getSpanPayload: ReturnType<typeof vi.fn>

function setupProvider(getPayload: (spanId: string) => Promise<SpanPayload>) {
  getSpanPayload = vi.fn((_modelId: string, _traceId: string, spanId: string) => getPayload(spanId))
  const provider = { getSpanAnnotations: vi.fn(async () => []), getSpanPayload }
  useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
}

function mountDialog(tree: TraceSpan[]) {
  return mount(TraceDialog, {
    props: {
      visible: true,
      tree,
      count: tree.length,
      maxSpanTime: 1000,
      minSpanTime: 0,
      artifactId: 'model-1',
      traceId: 't1',
    },
    global: {
      plugins: [[PrimeVue, { unstyled: true }]],
      directives: { tooltip: Tooltip },
      stubs: { Dialog: DialogStub, AnnotationsButton: true, AnnotationsView: true },
    },
  })
}

function payload(attributes: Record<string, string>): SpanPayload {
  return { attributes: JSON.stringify(attributes), events: null, links: null, status_message: null }
}

beforeEach(() => {
  vi.stubGlobal(
    'matchMedia',
    vi.fn(() => ({ matches: false, addEventListener: vi.fn(), removeEventListener: vi.fn() })),
  )
  mockVirtualLayout(670)
  setActivePinia(createPinia())
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('TraceDialog', () => {
  it('fetches a failed span payload again when the selected span is clicked again', async () => {
    let fail = true
    setupProvider(async (spanId) => {
      if (fail) throw new Error('read failed')
      return payload({ loaded: `value of ${spanId}` })
    })
    const wrapper = mountDialog([
      makeSpan('s1', { attributes: null as unknown as string, payloadLoaded: false }),
    ])
    await flushPromises()
    expect(wrapper.text()).toContain('Cannot load span data.')

    fail = false
    await wrapper.findComponent(TraceSpanRow).trigger('click')
    await flushPromises()

    expect(getSpanPayload).toHaveBeenCalledTimes(2)
    expect(wrapper.text()).not.toContain('Cannot load span data.')
    expect(wrapper.text()).toContain('value of s1')
  })

  it('does not fetch again when a loaded span is clicked again', async () => {
    setupProvider(async (spanId) => payload({ loaded: `value of ${spanId}` }))
    const wrapper = mountDialog([
      makeSpan('s1', { attributes: null as unknown as string, payloadLoaded: false }),
    ])
    await flushPromises()

    await wrapper.findComponent(TraceSpanRow).trigger('click')
    await flushPromises()

    expect(getSpanPayload).toHaveBeenCalledTimes(1)
    expect(wrapper.text()).toContain('value of s1')
  })

  it('keeps Escape from closing the trace while a value viewer is open', async () => {
    setupProvider(async () => payload({}))
    const wrapper = mountDialog([
      makeSpan('s1', { attributes: JSON.stringify({ big: 'x'.repeat(3_000) }) }),
    ])
    await flushPromises()
    const traceDialog = () => wrapper.findAllComponents(DialogStub)[0]!
    expect(traceDialog().props('closeOnEscape')).toBe(true)

    const showAll = wrapper.findAll('button').find((button) => button.text() === 'Show all')
    await showAll!.trigger('click')
    expect(traceDialog().props('closeOnEscape')).toBe(false)

    wrapper.findAllComponents(DialogStub)[1]!.vm.$emit('update:visible', false)
    await flushPromises()
    expect(traceDialog().props('closeOnEscape')).toBe(true)
  })
})
