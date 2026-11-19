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
