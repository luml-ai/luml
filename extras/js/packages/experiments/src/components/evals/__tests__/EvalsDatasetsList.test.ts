import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import type { EvalsInfo, ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import { useEvalsStore } from '@/store/evals'
import EvalsDatasetsList from '../EvalsDatasetsList.vue'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

enableAutoUnmount(afterEach)

function row(id: string) {
  return { id, dataset_id: 'd1', modelId: 'm1' } as unknown as EvalsInfo
}

function setupProvider() {
  const provider = {
    getUniqueDatasetsIds: vi.fn(async () => ['d1']),
    getEvalsColumns: vi.fn(async () => ({
      inputs: [],
      outputs: [],
      refs: [],
      scores: [],
      metadata: [],
    })),
    resetDatasetPage: vi.fn(async () => undefined),
    getNextEvalsByDatasetId: vi.fn(async (): Promise<EvalsInfo[]> => [row('e1')]),
    getEvalsDatasetAnnotationsSummary: vi.fn(async () => null),
    resetEvalsDatasetsRequestParams: vi.fn(async () => undefined),
  }
  useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  return provider
}

async function mountListWithFailedSort() {
  const provider = setupProvider()
  const wrapper = mount(EvalsDatasetsList, {
    shallow: true,
    props: { modelsInfo: {}, loaderHeight: '10px' },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  })
  await flushPromises()
  const vm = wrapper.vm as unknown as {
    getNextPage: (datasetId: string) => Promise<void>
    onSort: (datasetId: string, sortParams: object) => Promise<void>
  }
  provider.getNextEvalsByDatasetId.mockRejectedValueOnce(new Error('read failed'))
  await vm.onSort('d1', { sortField: 'scores.accuracy', sortOrder: 'asc' })
  await flushPromises()
  expect(provider.getNextEvalsByDatasetId).toHaveBeenCalledTimes(2)
  return { provider, vm }
}

function datasetRowIds() {
  return useEvalsStore().datasets?.[0]?.data.map((item) => item.id)
}

describe('EvalsDatasetsList after a failed sort reload', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reloads the dataset before it reads the next page', async () => {
    const { provider, vm } = await mountListWithFailedSort()
    provider.getNextEvalsByDatasetId
      .mockResolvedValueOnce([row('sorted-1')])
      .mockResolvedValueOnce([row('sorted-2')])

    await vm.getNextPage('d1')
    await flushPromises()

    expect(provider.resetDatasetPage).toHaveBeenCalledTimes(3)
    expect(provider.getNextEvalsByDatasetId).toHaveBeenCalledTimes(4)
    expect(provider.getNextEvalsByDatasetId).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort_by: 'scores.accuracy', order: 'asc' }),
    )
    expect(datasetRowIds()).toEqual(['sorted-1', 'sorted-2'])
    expect(useEvalsStore().loading).toBe(false)
  })

  it('tries a reload that keeps failing once per next page request', async () => {
    const { provider, vm } = await mountListWithFailedSort()
    provider.getNextEvalsByDatasetId.mockRejectedValue(new Error('read failed'))

    await vm.getNextPage('d1')
    await flushPromises()
    expect(provider.getNextEvalsByDatasetId).toHaveBeenCalledTimes(3)

    await vm.getNextPage('d1')
    await flushPromises()
    expect(provider.getNextEvalsByDatasetId).toHaveBeenCalledTimes(4)
    expect(datasetRowIds()).toEqual(['e1'])
    expect(useEvalsStore().loading).toBe(false)
  })
})

function deferred<T>() {
  let resolve!: (value: T) => void
  let reject!: (error: unknown) => void
  const promise = new Promise<T>((done, fail) => {
    resolve = done
    reject = fail
  })
  return { promise, resolve, reject }
}

function mountList() {
  const wrapper = mount(EvalsDatasetsList, {
    shallow: true,
    props: { modelsInfo: {}, loaderHeight: '10px' },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  })
  const vm = wrapper.vm as unknown as {
    getNextPage: (datasetId: string) => Promise<void>
    onSort: (datasetId: string, sortParams: object) => Promise<void>
  }
  return { wrapper, vm }
}

function readsOf(provider: ReturnType<typeof setupProvider>, datasetId: string) {
  const calls = provider.getNextEvalsByDatasetId.mock.calls as unknown as [{ dataset_id: string }][]
  return calls.filter(([params]) => params.dataset_id === datasetId).length
}

describe('EvalsDatasetsList kept next pages', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('reads the next kept page after the reload in place of the first one fails', async () => {
    const provider = setupProvider()
    provider.getUniqueDatasetsIds.mockResolvedValue(['d1', 'd2'])
    const { vm } = mountList()
    await flushPromises()
    provider.getNextEvalsByDatasetId.mockRejectedValueOnce(new Error('read failed'))
    await vm.onSort('d1', { sortField: 'scores.accuracy', sortOrder: 'asc' })
    await flushPromises()
    expect(readsOf(provider, 'd1')).toBe(2)
    expect(readsOf(provider, 'd2')).toBe(1)

    // d1's next page runs a reload in its place; d2's page is kept while it runs.
    const reload = deferred<EvalsInfo[]>()
    provider.getNextEvalsByDatasetId.mockReturnValueOnce(reload.promise)
    const reloadForPage = vm.getNextPage('d1')
    await flushPromises()
    vm.getNextPage('d2')
    reload.reject(new Error('read failed'))
    await reloadForPage
    await flushPromises()

    // d1's kept page is dropped after its reload failed; d2's page is still read.
    expect(readsOf(provider, 'd1')).toBe(3)
    expect(readsOf(provider, 'd2')).toBe(2)
    expect(useEvalsStore().loading).toBe(false)
  })

  it('retries a reload once for a page asked for while that reload was failing', async () => {
    const provider = setupProvider()
    const { vm } = mountList()
    await flushPromises()
    const reload = deferred<EvalsInfo[]>()
    provider.getNextEvalsByDatasetId.mockReturnValueOnce(reload.promise)
    const sort = vm.onSort('d1', { sortField: 'scores.accuracy', sortOrder: 'asc' })
    await flushPromises()
    provider.getNextEvalsByDatasetId.mockRejectedValue(new Error('read failed'))
    vm.getNextPage('d1')
    reload.reject(new Error('read failed'))
    await sort
    await flushPromises()

    // The first load, the failed reload and one retry.
    expect(provider.getNextEvalsByDatasetId).toHaveBeenCalledTimes(3)
    expect(datasetRowIds()).toEqual(['e1'])
    expect(useEvalsStore().loading).toBe(false)
  })
})

describe('EvalsDatasetsList closed after the next view reset the provider', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('closes without an error and releases nothing', async () => {
    const provider = setupProvider()
    const { wrapper } = mountList()
    await flushPromises()
    useEvalsStore().resetProvider()

    expect(() => wrapper.unmount()).not.toThrow()
    expect(provider.resetEvalsDatasetsRequestParams).not.toHaveBeenCalled()
  })

  it('releases the provider cursors when the provider is still set', async () => {
    const provider = setupProvider()
    const { wrapper } = mountList()
    await flushPromises()

    wrapper.unmount()
    expect(provider.resetEvalsDatasetsRequestParams).toHaveBeenCalledOnce()
  })
})
