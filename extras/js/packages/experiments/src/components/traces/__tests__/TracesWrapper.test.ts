import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'
import { Popover } from 'primevue'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import { useEvalsStore } from '@/store/evals'
import { useTraceStore } from '@/store/trace'
import TracesWrapper from '../TracesWrapper.vue'
import TableFilter from '../../table/filter/TableFilter.vue'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

enableAutoUnmount(afterEach)

const summary = { feedback: [], expectations: [] }

function setupProvider() {
  const provider = {
    getTraces: vi.fn(async () => []),
    resetTracesRequestParams: vi.fn(async () => undefined),
    getTracesAnnotationSummary: vi.fn(async () => summary),
    getTracesColumns: vi.fn(async () => ({
      attributes: [{ name: 'llm.model', type: 'string' }],
      annotations_feedback: [],
      annotations_expectations: [],
    })),
    validateTracesFilter: vi.fn(async () => []),
  }
  useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  return provider
}

function mountWrapper() {
  return mount(TracesWrapper, {
    props: { artifactId: 'model-1' },
    global: {
      plugins: [[PrimeVue, { unstyled: true }]],
      directives: { tooltip: Tooltip },
      stubs: { TracesTable: true },
    },
  })
}

function openFilterEditor(wrapper: ReturnType<typeof mountWrapper>) {
  wrapper.findComponent(TableFilter).findComponent(Popover).vm.$emit('show')
  return flushPromises()
}

describe('TracesWrapper filter keys', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('loads the filter keys once, when the filter editor first opens', async () => {
    const provider = setupProvider()
    const wrapper = mountWrapper()
    await flushPromises()

    expect(provider.getTraces).toHaveBeenCalled()
    expect(provider.getTracesColumns).not.toHaveBeenCalled()

    await openFilterEditor(wrapper)
    expect(provider.getTracesColumns).toHaveBeenCalledExactlyOnceWith('model-1')
    expect(useTraceStore().typedColumnsList).toEqual([
      { name: 'attributes.llm.model', type: 'string' },
    ])

    await openFilterEditor(wrapper)
    expect(provider.getTracesColumns).toHaveBeenCalledOnce()
  })

  it('loads the keys again after a failed attempt', async () => {
    const provider = setupProvider()
    provider.getTracesColumns.mockRejectedValueOnce(new Error('read failed'))
    const wrapper = mountWrapper()
    await flushPromises()

    await openFilterEditor(wrapper)
    await openFilterEditor(wrapper)

    expect(provider.getTracesColumns).toHaveBeenCalledTimes(2)
    expect(useTraceStore().typedColumnsList).toHaveLength(1)
  })
})
