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
import TracesTable from '../TracesTable.vue'
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

describe('TracesWrapper next page requests', () => {
  function deferred<T>() {
    let resolve!: (value: T) => void
    const promise = new Promise<T>((done) => (resolve = done))
    return { promise, resolve }
  }

  const page = Array.from({ length: 20 }, (_, index) => ({ trace_id: `t${index}` }))

  let summaryRead: ReturnType<typeof deferred<typeof summary>> | null

  function setupPagingProvider() {
    summaryRead = null
    const provider = setupProvider()
    provider.getTraces.mockImplementation(async () => page)
    provider.getTracesAnnotationSummary.mockImplementation(() =>
      summaryRead ? summaryRead.promise : Promise.resolve(summary),
    )
    return provider
  }

  function askForNextPage(wrapper: ReturnType<typeof mountWrapper>) {
    wrapper.findComponent(TracesTable).vm.$emit('get-next-page')
  }

  /** Changes the sort; the debounced reload ends with its annotation summary read held. */
  async function sortWithSummaryHeld(wrapper: ReturnType<typeof mountWrapper>) {
    summaryRead = deferred()
    wrapper.findComponent(TracesTable).vm.$emit('sort', {
      sortField: 'execution_time',
      sortOrder: 'desc',
    })
    await vi.advanceTimersByTimeAsync(500)
  }

  function sort(wrapper: ReturnType<typeof mountWrapper>, sortField: string, sortOrder: string) {
    wrapper.findComponent(TracesTable).vm.$emit('sort', { sortField, sortOrder })
  }

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('reads the next page asked for while a reload was still loading', async () => {
    const provider = setupPagingProvider()
    const wrapper = mountWrapper()
    await flushPromises()
    await sortWithSummaryHeld(wrapper)
    expect(provider.getTraces).toHaveBeenCalledTimes(2)

    askForNextPage(wrapper)
    await flushPromises()
    expect(useTraceStore().loading).toBe(true)
    expect(provider.getTraces).toHaveBeenCalledTimes(2)

    summaryRead!.resolve(summary)
    await flushPromises()

    expect(provider.getTraces).toHaveBeenCalledTimes(3)
    expect(provider.getTraces).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort_by: 'execution_time', order: 'desc' }),
    )
    expect(useTraceStore().traces).toHaveLength(40)
    expect(useTraceStore().loading).toBe(false)
  })

  it('reads the next page asked for before a sort reload only after that reload', async () => {
    const provider = setupPagingProvider()
    const wrapper = mountWrapper()
    await flushPromises()
    wrapper.findComponent(TracesTable).vm.$emit('sort', {
      sortField: 'execution_time',
      sortOrder: 'desc',
    })
    await flushPromises()

    askForNextPage(wrapper)
    await flushPromises()
    expect(provider.getTraces).toHaveBeenCalledTimes(1)

    await vi.advanceTimersByTimeAsync(500)
    await flushPromises()

    expect(provider.resetTracesRequestParams).toHaveBeenCalledTimes(2)
    expect(provider.getTraces).toHaveBeenCalledTimes(3)
    expect(provider.resetTracesRequestParams.mock.invocationCallOrder[1]).toBeLessThan(
      provider.getTraces.mock.invocationCallOrder[2]!,
    )
    expect(useTraceStore().traces).toHaveLength(40)
  })

  it('retries a failed sort reload when the next page is asked for, then reads the page', async () => {
    const provider = setupPagingProvider()
    const wrapper = mountWrapper()
    await flushPromises()
    provider.getTraces.mockRejectedValueOnce(new Error('read failed'))
    sort(wrapper, 'execution_time', 'desc')
    await vi.advanceTimersByTimeAsync(500)
    expect(provider.getTraces).toHaveBeenCalledTimes(2)
    expect(useTraceStore().loading).toBe(false)

    askForNextPage(wrapper)
    await flushPromises()
    expect(provider.getTraces).toHaveBeenCalledTimes(2)
    await vi.advanceTimersByTimeAsync(500)

    expect(provider.resetTracesRequestParams).toHaveBeenCalledTimes(3)
    expect(provider.getTraces).toHaveBeenCalledTimes(4)
    expect(provider.getTraces).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort_by: 'execution_time', order: 'desc' }),
    )
    expect(useTraceStore().traces).toHaveLength(40)
    await vi.advanceTimersByTimeAsync(5000)
    expect(provider.getTraces).toHaveBeenCalledTimes(4)
  })

  it('tries a reload that keeps failing once per next page request', async () => {
    const provider = setupPagingProvider()
    const wrapper = mountWrapper()
    await flushPromises()
    provider.getTraces.mockRejectedValue(new Error('read failed'))
    sort(wrapper, 'execution_time', 'desc')
    await vi.advanceTimersByTimeAsync(500)
    expect(provider.getTraces).toHaveBeenCalledTimes(2)

    askForNextPage(wrapper)
    await vi.advanceTimersByTimeAsync(5000)
    expect(provider.getTraces).toHaveBeenCalledTimes(3)

    askForNextPage(wrapper)
    await vi.advanceTimersByTimeAsync(5000)
    expect(provider.getTraces).toHaveBeenCalledTimes(4)
    expect(useTraceStore().traces).toHaveLength(20)
    expect(useTraceStore().loading).toBe(false)
  })

  it('reads one page for two requests kept during a reload', async () => {
    const provider = setupPagingProvider()
    const wrapper = mountWrapper()
    await flushPromises()
    await sortWithSummaryHeld(wrapper)
    askForNextPage(wrapper)
    askForNextPage(wrapper)
    await flushPromises()

    summaryRead!.resolve(summary)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(5000)

    expect(provider.getTraces).toHaveBeenCalledTimes(3)
    expect(useTraceStore().traces).toHaveLength(40)
  })

  it('sends no kept request after the view closed', async () => {
    const provider = setupPagingProvider()
    const wrapper = mountWrapper()
    await flushPromises()
    await sortWithSummaryHeld(wrapper)
    askForNextPage(wrapper)
    await flushPromises()

    wrapper.unmount()
    summaryRead!.resolve(summary)
    await flushPromises()
    await vi.advanceTimersByTimeAsync(5000)

    expect(provider.getTraces).toHaveBeenCalledTimes(2)
  })

  it('reads no extra page for a request kept before the sort went back', async () => {
    const provider = setupPagingProvider()
    const wrapper = mountWrapper()
    await flushPromises()
    sort(wrapper, 'execution_time', 'desc')
    await flushPromises()
    askForNextPage(wrapper)
    await flushPromises()
    sort(wrapper, 'created_at', 'desc')
    await flushPromises()

    askForNextPage(wrapper)
    await flushPromises()
    expect(provider.getTraces).toHaveBeenCalledTimes(2)
    expect(useTraceStore().traces).toHaveLength(40)

    await vi.advanceTimersByTimeAsync(500)
    expect(provider.getTraces).toHaveBeenCalledTimes(3)
    expect(useTraceStore().traces).toHaveLength(20)
  })

  it('reads no page with the cursor of a sort reload that was dropped', async () => {
    const provider = setupPagingProvider()
    const wrapper = mountWrapper()
    await flushPromises()
    const reloadRead = deferred<typeof page>()
    provider.getTraces.mockImplementationOnce(() => reloadRead.promise)
    sort(wrapper, 'execution_time', 'desc')
    await vi.advanceTimersByTimeAsync(500)
    expect(provider.resetTracesRequestParams).toHaveBeenCalledTimes(2)

    sort(wrapper, 'created_at', 'desc')
    reloadRead.resolve(page)
    await flushPromises()
    expect(useTraceStore().loading).toBe(false)

    askForNextPage(wrapper)
    await flushPromises()
    expect(provider.getTraces).toHaveBeenCalledTimes(2)

    await vi.advanceTimersByTimeAsync(500)
    expect(provider.resetTracesRequestParams).toHaveBeenCalledTimes(3)
    expect(provider.getTraces).toHaveBeenCalledTimes(4)
    expect(provider.resetTracesRequestParams.mock.invocationCallOrder[2]).toBeLessThan(
      provider.getTraces.mock.invocationCallOrder[2]!,
    )
    expect(useTraceStore().traces).toHaveLength(40)
  })
})

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
