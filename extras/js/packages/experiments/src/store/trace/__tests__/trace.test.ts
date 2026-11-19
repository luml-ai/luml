import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import { useEvalsStore } from '../../evals'
import { useTraceStore } from '..'

const toastAdd = vi.hoisted(() => vi.fn())

vi.mock('primevue', () => ({ useToast: () => ({ add: toastAdd }) }))

describe('trace store', () => {
  let calls: string[]

  beforeEach(() => {
    calls = []
    setActivePinia(createPinia())
    const provider = {
      resetTracesRequestParams() {
        calls.push('resetTracesRequestParams')
        return Promise.reject(new Error('worker was terminated'))
      },
      getTraces() {
        calls.push('getTraces')
        // The cursor was not reset, so this is not the first page.
        return Promise.resolve([{ trace_id: 'row-of-page-2' }])
      },
    }
    useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  })

  it('leaves no pending search or error toast after leaving Traces', async () => {
    vi.useFakeTimers()
    try {
      const store = useTraceStore()
      store.setArtifactId('m1')
      store.setRequestParams({ search: 'validation' })
      await nextTick()
      store.reset()
      useEvalsStore().resetProvider()
      await nextTick()
      await vi.runAllTimersAsync()
      expect(toastAdd).not.toHaveBeenCalled()
      expect(calls).not.toContain('getTraces')
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not leave a failed provider reset unhandled on store reset', async () => {
    useTraceStore().reset()
    await new Promise((resolve) => setTimeout(resolve))

    expect(calls).toEqual(['resetTracesRequestParams'])
  })

  it('fails a reload whose provider reset failed, without listing rows of the old cursor', async () => {
    const store = useTraceStore()

    await expect(store.getNextPage(true)).rejects.toThrow('worker was terminated')

    expect(calls).toEqual(['resetTracesRequestParams', 'getTraces'])
    expect(store.traces).toEqual([])
    expect(store.isListCurrent()).toBe(false)
  })

  it('resets without an error after the next view reset the provider', () => {
    const store = useTraceStore()
    store.setArtifactId('model-1')
    useEvalsStore().resetProvider()

    expect(() => store.reset()).not.toThrow()
    expect(calls).toEqual([])
    expect(store.requestParams.search).toBe('')
  })
})

describe('trace store reload after a parameter change', () => {
  const DEBOUNCE_MS = 500

  function fakeProvider() {
    return {
      resetTracesRequestParams: vi.fn(() => Promise.resolve()),
      getTraces: vi.fn(() => Promise.resolve([])),
      getTracesAnnotationSummary: vi.fn(() => Promise.resolve(null)),
    }
  }

  let provider: ReturnType<typeof fakeProvider>

  beforeEach(() => {
    vi.useFakeTimers()
    toastAdd.mockClear()
    setActivePinia(createPinia())
    provider = fakeProvider()
    useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  /** The view closing: the trace list resets, then the snapshot view drops its provider. */
  async function closeView() {
    useTraceStore().reset()
    useEvalsStore().resetProvider()
    await nextTick()
  }

  it('reloads once after the debounce when the parameters of an open experiment change', async () => {
    const store = useTraceStore()
    store.setArtifactId('m1')
    store.setRequestParams({ search: 'a' })
    await nextTick()
    store.setRequestParams({ search: 'ab' })
    await nextTick()

    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS - 1)
    expect(provider.getTraces).not.toHaveBeenCalled()
    await vi.advanceTimersByTimeAsync(1)
    expect(provider.getTraces).toHaveBeenCalledTimes(1)
    expect(provider.getTraces).toHaveBeenCalledWith(expect.objectContaining({ search: 'ab' }))
  })

  it('schedules no reload when the store resets as its view closes', async () => {
    useTraceStore().setArtifactId('m1')
    await closeView()
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2)

    expect(provider.getTraces).not.toHaveBeenCalled()
    expect(toastAdd).not.toHaveBeenCalled()
  })

  it('drops a reload scheduled just before the view closed', async () => {
    const store = useTraceStore()
    store.setArtifactId('m1')
    store.setRequestParams({ search: 'a' })
    await nextTick()
    await closeView()
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2)

    expect(provider.getTraces).not.toHaveBeenCalled()
    expect(toastAdd).not.toHaveBeenCalled()
  })

  it('never reloads the closed experiment when another one opens within the debounce', async () => {
    const store = useTraceStore()
    store.setArtifactId('m1')
    store.setRequestParams({ search: 'a' })
    await nextTick()
    await closeView()
    const next = fakeProvider()
    useEvalsStore().setProvider(next as unknown as ExperimentSnapshotProvider)
    store.setArtifactId('m2')
    await vi.advanceTimersByTimeAsync(DEBOUNCE_MS * 2)

    expect(provider.getTraces).not.toHaveBeenCalled()
    // The reload scheduled before the close may still run, for the experiment now open.
    expect(next.getTraces.mock.calls.length).toBeLessThanOrEqual(1)
    expect(toastAdd).not.toHaveBeenCalled()
  })
})

describe('trace store answers that arrive late', () => {
  type Rows = { trace_id: string }[]

  function deferred<T>() {
    let resolve!: (value: T) => void
    const promise = new Promise<T>((done) => (resolve = done))
    return { promise, resolve }
  }

  function heldProvider() {
    const pending: ReturnType<typeof deferred<Rows>>[] = []
    const hold = () => {
      const read = deferred<Rows>()
      pending.push(read)
      return read.promise
    }
    return {
      pending,
      resetTracesRequestParams: vi.fn(() => Promise.resolve()),
      getTraces: vi.fn(hold),
      getFreshTraces: vi.fn(hold),
      getTracesAnnotationSummary: vi.fn(() => Promise.resolve(null)),
    }
  }

  const rows = (...ids: string[]): Rows => ids.map((trace_id) => ({ trace_id }))
  const traceIds = () => useTraceStore().traces.map((trace) => trace.trace_id)

  let provider: ReturnType<typeof heldProvider>

  beforeEach(() => {
    vi.useFakeTimers()
    toastAdd.mockClear()
    setActivePinia(createPinia())
    provider = heldProvider()
    useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('writes nothing when a page arrives after the store was reset', async () => {
    const store = useTraceStore()
    store.setArtifactId('m1')
    const page = store.getNextPage(true)
    store.reset()
    provider.pending[0]!.resolve(rows('a1'))
    await page

    expect(store.traces).toEqual([])
    expect(provider.getTracesAnnotationSummary).not.toHaveBeenCalled()
  })

  it('keeps the rows of the next experiment when the closed one answers last', async () => {
    const store = useTraceStore()
    store.setArtifactId('m1')
    const closedPage = store.getNextPage(true)
    store.reset()
    store.setArtifactId('m2')
    const openPage = store.getNextPage(true)
    provider.pending[1]!.resolve(rows('b1', 'b2'))
    await openPage
    provider.pending[0]!.resolve(rows('a1'))
    await closedPage

    expect(traceIds()).toEqual(['b1', 'b2'])
  })

  it('does not clear the loading flag of the next view when a refresh of the closed one ends', async () => {
    const store = useTraceStore()
    store.setArtifactId('m1')
    const refresh = store.refresh()
    store.reset()
    store.setArtifactId('m2')
    store.setLoading(true)
    provider.pending[0]!.resolve(rows('a1'))
    await refresh

    expect(store.loading).toBe(true)
    expect(store.traces).toEqual([])
  })

  it('reloads with the new sort when it changed while a page was loading', async () => {
    const store = useTraceStore()
    store.setArtifactId('m1')
    // The list view loads the next page.
    store.setLoading(true)
    const page = store.getNextPage()
    store.setRequestParams({ sort_by: 'execution_time', order: 'asc' })
    await nextTick()
    await vi.advanceTimersByTimeAsync(500)
    provider.pending[0]!.resolve(rows('old-sort'))
    await page
    store.setLoading(false)
    await nextTick()

    expect(store.traces).toEqual([])
    expect(provider.getTraces).toHaveBeenCalledTimes(2)
    expect(provider.getTraces).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort_by: 'execution_time', order: 'asc' }),
    )
    provider.pending[1]!.resolve(rows('new-sort'))
    await vi.advanceTimersByTimeAsync(0)

    expect(traceIds()).toEqual(['new-sort'])
    expect(store.loading).toBe(false)
    expect(toastAdd).not.toHaveBeenCalled()
  })
})
