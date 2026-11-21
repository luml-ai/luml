import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import type { ExperimentSnapshotProvider, ModelScores } from '@/interfaces/interfaces'
import { INITIAL_PARAMS } from '@/store/evals/evals.data'
import { useEvalsStore } from '@/store/evals'
import EvalsDataset from '../EvalsDataset.vue'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

enableAutoUnmount(afterEach)

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => (resolve = done))
  return { promise, resolve }
}

const scores = (value: number): ModelScores[] =>
  [{ modelId: 'm1', scores: [{ name: 'accuracy', value }] }] as unknown as ModelScores[]

const columns = { inputs: [], outputs: [], refs: [], scores: [], metadata: [] }

function setupProvider() {
  const averageReads: ReturnType<typeof deferred<ModelScores[]>>[] = []
  const provider = {
    getDatasetAverageScores: vi.fn(() => {
      const read = deferred<ModelScores[]>()
      averageReads.push(read)
      return read.promise
    }),
    getFreshEvalsByDatasetId: vi.fn(async () => [{ id: 'fresh' }]),
    getEvalsDatasetAnnotationsSummary: vi.fn(async () => null),
  }
  const store = useEvalsStore()
  store.setProvider(provider as unknown as ExperimentSnapshotProvider)
  store.datasets = [
    {
      columns,
      data: [{ id: 'old' }],
      params: { ...INITIAL_PARAMS, dataset_id: 'd1' },
    } as unknown as NonNullable<ReturnType<typeof useEvalsStore>['datasets']>[number],
  ]
  return { provider, averageReads }
}

function mountDataset() {
  const wrapper = mount(EvalsDataset, {
    shallow: true,
    props: { datasetId: 'd1', data: [], modelsInfo: {}, columns },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  })
  return {
    wrapper,
    averages: () =>
      (wrapper.vm as unknown as { averageScores: ModelScores[] | null }).averageScores,
  }
}

describe('EvalsDataset average scores', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('reads the averages again after a refresh replaced the rows', async () => {
    const { provider, averageReads } = setupProvider()
    const { averages } = mountDataset()
    averageReads[0]!.resolve(scores(0.5))
    await flushPromises()
    expect(averages()).toEqual(scores(0.5))

    await useEvalsStore().refresh()
    await flushPromises()
    expect(provider.getDatasetAverageScores).toHaveBeenCalledTimes(2)
    averageReads[1]!.resolve(scores(0.75))
    await flushPromises()

    expect(averages()).toEqual(scores(0.75))
  })

  it('reads the averages once when nothing is refreshed', async () => {
    const { provider } = setupProvider()
    mountDataset()
    await vi.advanceTimersByTimeAsync(5000)

    expect(provider.getDatasetAverageScores).toHaveBeenCalledOnce()
  })

  it('keeps the averages for the latest search when an older read answers last', async () => {
    const { provider, averageReads } = setupProvider()
    const { wrapper, averages } = mountDataset()
    averageReads[0]!.resolve(scores(0.5))
    await flushPromises()

    await useEvalsStore().refresh()
    await flushPromises()
    ;(wrapper.vm as unknown as { filter: { search: string } }).filter.search = 'paris'
    await vi.advanceTimersByTimeAsync(300)
    expect(provider.getDatasetAverageScores).toHaveBeenCalledTimes(3)
    expect(provider.getDatasetAverageScores).toHaveBeenLastCalledWith('d1', 'paris', [])

    averageReads[2]!.resolve(scores(0.9))
    await flushPromises()
    averageReads[1]!.resolve(scores(0.75))
    await flushPromises()

    expect(averages()).toEqual(scores(0.9))
  })

  it('writes no averages that arrive after the view closed', async () => {
    const { averageReads } = setupProvider()
    const { wrapper, averages } = mountDataset()
    averageReads[0]!.resolve(scores(0.5))
    await flushPromises()
    await useEvalsStore().refresh()
    await flushPromises()

    wrapper.unmount()
    averageReads[1]!.resolve(scores(0.75))
    await flushPromises()

    expect(averages()).toEqual(scores(0.5))
  })
})
