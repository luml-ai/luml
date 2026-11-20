import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { flushPromises } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import { INITIAL_PARAMS } from '../evals.data'
import { useAnnotationsStore } from '../../annotations'
import { useEvalsStore } from '..'

const toastAdd = vi.hoisted(() => vi.fn())

vi.mock('primevue', () => ({ useToast: () => ({ add: toastAdd }) }))

type Rows = { id: string }[]

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => (resolve = done))
  return { promise, resolve }
}

/** Every eval page read is held until the test resolves it. */
function heldProvider(datasetsIds: string[] = ['d1']) {
  const pages: ReturnType<typeof deferred<Rows>>[] = []
  const hold = () => {
    const read = deferred<Rows>()
    pages.push(read)
    return read.promise
  }
  return {
    pages,
    getUniqueDatasetsIds: vi.fn(() => Promise.resolve(datasetsIds)),
    getEvalsColumns: vi.fn(() => Promise.resolve({ inputs: [] })),
    resetDatasetPage: vi.fn(() => Promise.resolve()),
    getNextEvalsByDatasetId: vi.fn(hold),
    getFreshEvalsByDatasetId: vi.fn(hold),
    getEvalsDatasetAnnotationsSummary: vi.fn((datasetId: string) => Promise.resolve({ datasetId })),
  }
}

const rows = (...ids: string[]): Rows => ids.map((id) => ({ id }))

function setProvider(provider: ReturnType<typeof heldProvider>) {
  useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
}

function datasetRows() {
  return useEvalsStore().datasets?.map((dataset) => [
    dataset.params.dataset_id,
    dataset.data.map((row) => row.id),
  ])
}

function addDataset(datasetId: string, ids: string[]) {
  useEvalsStore().datasets = [
    {
      columns: { inputs: [], outputs: [], refs: [], scores: [], metadata: [] },
      data: rows(...ids),
      params: { ...INITIAL_PARAMS, dataset_id: datasetId },
    } as unknown as NonNullable<ReturnType<typeof useEvalsStore>['datasets']>[number],
  ]
}

describe('evals store answers that arrive late', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    toastAdd.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('writes no dataset when it arrives after the store was reset', async () => {
    const provider = heldProvider()
    setProvider(provider)
    const store = useEvalsStore()
    const init = store.initDatasets()
    await flushPromises()
    expect(provider.pages).toHaveLength(1)
    store.reset()
    provider.pages[0]!.resolve(rows('a1'))
    await init

    expect(store.datasets).toBeNull()
    expect(provider.getEvalsDatasetAnnotationsSummary).not.toHaveBeenCalled()
  })

  it('does not mix the datasets of the closed experiment into the next one', async () => {
    const closed = heldProvider(['closed-dataset'])
    setProvider(closed)
    const store = useEvalsStore()
    const closedInit = store.initDatasets()
    await flushPromises()
    expect(closed.pages).toHaveLength(1)
    store.reset()
    const next = heldProvider(['next-dataset'])
    setProvider(next)
    const nextInit = store.initDatasets()
    await flushPromises()
    expect(next.pages).toHaveLength(1)
    next.pages[0]!.resolve(rows('b1'))
    await nextInit
    closed.pages[0]!.resolve(rows('a1'))
    await closedInit

    expect(datasetRows()).toEqual([['next-dataset', ['b1']]])
  })

  it('drops a page that arrives after the provider changed', async () => {
    const closed = heldProvider()
    setProvider(closed)
    addDataset('d1', ['b1'])
    const store = useEvalsStore()
    const page = store.getNextDatasetPage('d1')
    await flushPromises()
    expect(closed.pages).toHaveLength(1)
    setProvider(heldProvider())
    closed.pages[0]!.resolve(rows('a1'))
    await page

    expect(datasetRows()).toEqual([['d1', ['b1']]])
  })

  it('drops a page read for a sort that changed meanwhile', async () => {
    const provider = heldProvider()
    setProvider(provider)
    addDataset('d1', ['first'])
    const store = useEvalsStore()
    const page = store.getNextDatasetPage('d1')
    await flushPromises()
    expect(provider.pages).toHaveLength(1)
    store.datasets![0]!.params.sort_by = 'other'
    provider.pages[0]!.resolve(rows('old-sort'))
    await page

    expect(datasetRows()).toEqual([['d1', ['first']]])
  })

  it('a refresh that ends after a reset writes nothing and shows no error', async () => {
    const provider = heldProvider()
    setProvider(provider)
    addDataset('d1', ['first'])
    const store = useEvalsStore()
    const refresh = store.refresh()
    store.reset()
    // The next experiment's list is loading already.
    store.setLoading(true)
    provider.pages[0]!.resolve(rows('late'))
    await refresh

    expect(store.datasets).toBeNull()
    expect(store.loading).toBe(true)
    expect(toastAdd).not.toHaveBeenCalled()
  })
})

describe('annotations store answers that arrive late', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('keeps the newer traces summary when an older read answers last', async () => {
    const older = deferred<object>()
    const newer = deferred<object>()
    const getTracesAnnotationSummary = vi
      .fn()
      .mockReturnValueOnce(older.promise)
      .mockReturnValueOnce(newer.promise)
    useEvalsStore().setProvider({
      getTracesAnnotationSummary,
    } as unknown as ExperimentSnapshotProvider)
    const store = useAnnotationsStore()
    const olderRead = store.getTracesAnnotationSummary('closed')
    const newerRead = store.getTracesAnnotationSummary('open')
    newer.resolve({ experiment: 'open' })
    await newerRead
    older.resolve({ experiment: 'closed' })
    await olderRead

    expect(store.tracesAnnotationsSummary).toEqual({ experiment: 'open' })
  })
})
