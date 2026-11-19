import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import { INITIAL_PARAMS } from '../evals.data'
import { useAnnotationsStore } from '../../annotations'
import { useEvalsStore } from '..'

vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))

const annotation = { id: 'a1', name: 'correct', value: true }

function setupProvider() {
  const provider = {
    getEvalsColumns: vi.fn(async () => ({ inputs: [] })),
    resetDatasetPage: vi.fn(async () => undefined),
    getNextEvalsByDatasetId: vi.fn(async () => [{ id: 'match' }]),
    getEvalsDatasetAnnotationsSummary: vi.fn(async () => null),
    createEvalAnnotation: vi.fn(async () => annotation),
    updateEvalAnnotation: vi.fn(async () => annotation),
    deleteEvalAnnotation: vi.fn(async () => undefined),
  }
  useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  return provider
}

const searchedParams = {
  ...INITIAL_PARAMS,
  dataset_id: 'd1',
  limit: 50,
  search: 'paris',
  filters: ['scores.accuracy > 0.5'],
  sort_by: 'scores.accuracy',
  order: 'asc',
}

function addSearchedDataset() {
  useEvalsStore().datasets = [
    {
      columns: { inputs: [] },
      data: [{ id: 'match' }],
      params: { ...searchedParams, filters: [...searchedParams.filters] },
    } as unknown as NonNullable<ReturnType<typeof useEvalsStore>['datasets']>[number],
  ]
}

describe('eval annotation changes with a search active', () => {
  let provider: ReturnType<typeof setupProvider>

  beforeEach(() => {
    setActivePinia(createPinia())
    provider = setupProvider()
    addSearchedDataset()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  function expectFirstPageWithSearch() {
    expect(provider.resetDatasetPage).toHaveBeenCalledExactlyOnceWith('d1')
    expect(provider.getNextEvalsByDatasetId).toHaveBeenCalledExactlyOnceWith(searchedParams)
    expect(useEvalsStore().datasets?.[0]?.params).toEqual(searchedParams)
    expect(useEvalsStore().isDatasetCurrent('d1')).toBe(true)
  }

  it('reloads the first page with the search after an annotation is added', async () => {
    const annotations = useAnnotationsStore()
    annotations.openAddDialog({ artifactId: 'm1', datasetId: 'd1', evalId: 'e1' })
    await annotations.addEvalAnnotation({ name: 'correct', value: true } as never)

    expectFirstPageWithSearch()
  })

  it('reloads the first page with the search after an annotation is updated', async () => {
    await useAnnotationsStore().updateEvalAnnotation('m1', 'd1', 'a1', { value: false } as never)

    expectFirstPageWithSearch()
  })

  it('reloads the first page with the search after an annotation is deleted', async () => {
    await useAnnotationsStore().deleteEvalAnnotation('m1', 'd1', 'a1')

    expectFirstPageWithSearch()
  })
})
