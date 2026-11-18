import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { computed, nextTick, ref, type Component } from 'vue'
import PrimeVue from 'primevue/config'
import Tooltip from 'primevue/tooltip'
import type {
  EvalsInfo,
  ExperimentSnapshotProvider,
  GetTracesParams,
  TraceSpan,
} from '@/interfaces/interfaces'
import { ExperimentSnapshotWorkerProxy } from '@/providers/ExperimentSnapshotWorkerProxy'
import { useEvalsStore } from '@/store/evals'
import { INITIAL_PARAMS } from '@/store/evals/evals.data'
import { useTraceStore } from '@/store/trace'
import { useTracesTable } from '@/hooks/useTracesTable'
import { useEvalsTable } from '@/hooks/useEvalsTable'
import ExperimentSnapshot from '@/ExperimentSnapshot.vue'
import EvalsDataset from '@/components/evals/EvalsDataset.vue'
import EvalsDatasetsList from '@/components/evals/EvalsDatasetsList.vue'
import TracesDialog from '@/components/evals/traces/TracesDialog.vue'
import TracesModel from '@/components/evals/traces/models/TracesModel.vue'
import TraceBody from '@/components/evals/traces/trace/body/TraceBody.vue'
import TableFilter from '@/components/table/filter/TableFilter.vue'
import TracesTable from '@/components/traces/TracesTable.vue'
import TracesToolbar from '@/components/traces/TracesToolbar.vue'
import TracesWrapper from '@/components/traces/TracesWrapper.vue'
import { makeSpan } from '@/components/evals/traces/trace/__tests__/spanFactory'

const toastAdd = vi.hoisted(() => vi.fn())

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: toastAdd }),
}))

// PrimeVue components start timers on mount that must not fire after jsdom teardown.
enableAutoUnmount(afterEach)

type WorkerState = 'terminated' | 'crashed'

class FakeWorker extends EventTarget {
  readonly terminate = vi.fn()
  postMessage = vi.fn()
}

/** A proxy terminated on purpose, or one whose worker crashes on every request. */
function workerProxy(state: WorkerState) {
  const worker = new FakeWorker()
  const proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker)
  if (state === 'terminated') proxy.terminate()
  else {
    worker.postMessage = vi.fn(() => {
      worker.dispatchEvent(new ErrorEvent('error', { message: 'worker crashed' }))
    })
  }
  useEvalsStore().setProvider(proxy)
  return proxy
}

const uncaughtInView = vi.fn()

const mountOptions = {
  shallow: true,
  global: {
    plugins: [[PrimeVue, { unstyled: true }]] as [typeof PrimeVue, object][],
    directives: { tooltip: Tooltip },
    // An error a hook leaves uncaught reaches the app handler, which logs it.
    config: { errorHandler: uncaughtInView },
  },
}

function mountView(component: Component, props: Record<string, unknown> = {}) {
  return mount(component, { ...mountOptions, props })
}

/** Script-setup functions that no stubbed child can trigger. */
function setupFunction(wrapper: ReturnType<typeof mount>, name: string) {
  return (wrapper.vm as unknown as Record<string, (...args: unknown[]) => Promise<unknown>>)[name]!
}

const evalRow = {
  id: 'e1',
  dataset_id: 'd1',
  modelId: 'm1',
  inputs: {},
  outputs: {},
  refs: {},
  scores: {},
  metadata: {},
  annotations: null,
} as unknown as EvalsInfo

function addDataset() {
  const store = useEvalsStore()
  store.datasets = [
    {
      columns: { inputs: [], outputs: [], refs: [], scores: [], metadata: [] },
      data: [],
      params: { ...INITIAL_PARAMS, dataset_id: 'd1' },
    } as unknown as NonNullable<typeof store.datasets>[number],
  ]
}

const tracesParams = { limit: 20, search: '', filters: [] } as unknown as GetTracesParams

const sites: { site: string; detail: string; run: () => Promise<unknown> }[] = [
  {
    site: 'static params of the snapshot view',
    detail: 'Failed to load static params',
    run: async () => {
      mountView(ExperimentSnapshot, {
        provider: useEvalsStore().getProvider,
        modelsIds: ['m1'],
        modelsInfo: {},
        theme: 'light',
      })
    },
  },
  {
    site: 'evals store refresh',
    detail: 'worker crashed',
    run: () => {
      addDataset()
      return useEvalsStore().refresh()
    },
  },
  {
    site: 'trace store refresh',
    detail: 'worker crashed',
    run: () => useTraceStore().refresh(),
  },
  {
    site: 'trace store request params change',
    detail: 'worker crashed',
    run: async () => {
      vi.useFakeTimers()
      try {
        useTraceStore().setArtifactId('m1')
        useTraceStore().setRequestParams({ search: 'x' })
        await nextTick()
        await vi.advanceTimersByTimeAsync(500)
      } finally {
        vi.useRealTimers()
      }
    },
  },
  {
    site: 'traces CSV export',
    detail: 'worker crashed',
    run: () => useTracesTable(ref([]), ref([]), ref(tracesParams)).exportCSV(),
  },
  {
    site: 'evals CSV export',
    detail: 'worker crashed',
    run: () =>
      useEvalsTable(
        computed(() => []),
        ref(''),
        'd1',
        ref([]),
        ref([]),
      ).exportCSV(),
  },
  {
    site: 'traces table trace link',
    detail: 'worker crashed',
    run: () => {
      const wrapper = mountView(TracesTable, { data: [], selectedColumns: [], artifactId: 'm1' })
      return setupFunction(wrapper, 'showTrace')('t1')
    },
  },
  {
    site: 'traces table eval link',
    detail: 'worker crashed',
    run: () => {
      const wrapper = mountView(TracesTable, { data: [], selectedColumns: [], artifactId: 'm1' })
      return setupFunction(wrapper, 'showEval')('e1', ['e1'])
    },
  },
  {
    site: 'traces toolbar filter keys',
    detail: 'worker crashed',
    run: () => {
      useTraceStore().setArtifactId('m1')
      const wrapper = mountView(TracesToolbar, {
        columns: [],
        selectedColumns: [],
        exportLoading: false,
      })
      wrapper.findComponent(TableFilter).vm.$emit('open')
      return flushPromises()
    },
  },
  {
    site: 'traces wrapper first page',
    detail: 'worker crashed',
    run: () => {
      mountView(TracesWrapper, { artifactId: 'm1' })
      return flushPromises()
    },
  },
  {
    site: 'evals datasets list',
    detail: 'worker crashed',
    run: () => {
      mountView(EvalsDatasetsList, { modelsInfo: {}, loaderHeight: '10px' })
      return flushPromises()
    },
  },
  {
    site: 'evals datasets list next page',
    detail: 'worker crashed',
    run: async () => {
      const wrapper = mountView(EvalsDatasetsList, { modelsInfo: {}, loaderHeight: '10px' })
      await flushPromises()
      toastAdd.mockClear()
      addDataset()
      return setupFunction(wrapper, 'getNextPage')('d1')
    },
  },
  {
    site: 'evals dataset average scores',
    detail: 'worker crashed',
    run: () => {
      mountView(EvalsDataset, {
        data: [],
        modelsInfo: {},
        columns: { inputs: [], outputs: [], refs: [], scores: [], metadata: [] },
        datasetId: 'd1',
      })
      return flushPromises()
    },
  },
  {
    site: 'eval dialog annotations',
    detail: 'worker crashed',
    run: () => {
      useEvalsStore().setCurrentEvalData([evalRow])
      mountView(TracesModel, { id: 'm1', name: 'model' })
      return flushPromises()
    },
  },
  {
    site: 'eval dialog trace button',
    detail: 'Failed to load spans',
    run: async () => {
      useEvalsStore().setCurrentEvalData([evalRow])
      const wrapper = mountView(TracesModel, { id: 'm1', name: 'model' })
      await flushPromises()
      toastAdd.mockClear()
      return setupFunction(wrapper, 'showSpans')()
    },
  },
  {
    site: 'eval dialog navigation',
    detail: 'worker crashed',
    run: () => {
      useEvalsStore().setCurrentEvalData([evalRow])
      const wrapper = mountView(TracesDialog, { modelsInfo: {} })
      return setupFunction(wrapper, 'onCurrentEvalIdUpdate')('e2')
    },
  },
  {
    site: 'span annotations',
    detail: 'worker crashed',
    run: () => {
      const span: TraceSpan = makeSpan('s1')
      mountView(TraceBody, { data: span, artifactId: 'm1', traceId: 't1' })
      return flushPromises()
    },
  },
  {
    site: 'filter validation',
    detail: 'worker crashed',
    run: () => {
      const proxy = useEvalsStore().getProvider
      const wrapper = mountView(TableFilter, {
        fields: [],
        asyncValidateCallback: () => proxy.validateTracesFilter([]),
      })
      return setupFunction(wrapper, 'asyncValidate')()
    },
  },
]

describe('reads of a closed experiment', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it.each(sites)('$site shows no toast when the worker was terminated', async ({ run }) => {
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => {})
    workerProxy('terminated')
    await run()
    await flushPromises()

    expect(toastAdd).not.toHaveBeenCalled()
    expect(uncaughtInView).not.toHaveBeenCalled()
    expect(consoleError).not.toHaveBeenCalled()
  })

  it.each(sites)('$site still reports a worker that crashed', async ({ run, detail }) => {
    workerProxy('crashed')
    await run()
    await flushPromises()

    expect(toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error', detail }))
  })

  it('shows no toast when the snapshot view closes with its static params in flight', async () => {
    const proxy = new ExperimentSnapshotWorkerProxy(new FakeWorker() as unknown as Worker)
    useEvalsStore().setProvider(proxy)
    const wrapper = mountView(ExperimentSnapshot, {
      provider: proxy,
      modelsIds: ['m1'],
      modelsInfo: {},
      theme: 'light',
    })
    await flushPromises()
    wrapper.unmount()
    await flushPromises()

    expect(toastAdd).not.toHaveBeenCalled()
  })
})

describe('a view that closed', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    toastAdd.mockClear()
    uncaughtInView.mockClear()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.restoreAllMocks()
  })

  it('the traces wrapper goes no further when its first page was dropped by the close', async () => {
    const worker = new FakeWorker()
    const proxy = new ExperimentSnapshotWorkerProxy(worker as unknown as Worker)
    const evalsStore = useEvalsStore()
    evalsStore.setProvider(proxy)
    const summary = vi.spyOn(proxy, 'getTracesAnnotationSummary')
    const wrapper = mountView(TracesWrapper, { artifactId: 'm1' })
    await flushPromises()

    wrapper.unmount()
    evalsStore.resetProvider()
    // The next experiment's trace list is loading already.
    useTraceStore().setLoading(true)
    proxy.terminate()
    await flushPromises()

    expect(summary).not.toHaveBeenCalled()
    expect(useTraceStore().loading).toBe(true)
    expect(toastAdd).not.toHaveBeenCalled()
    expect(uncaughtInView).not.toHaveBeenCalled()
  })

  it('an evals dataset drops the filter reload it scheduled just before the close', async () => {
    vi.useFakeTimers()
    const averageScores = vi.fn(() => Promise.resolve({}))
    const evalsStore = useEvalsStore()
    evalsStore.setProvider({
      getDatasetAverageScores: averageScores,
    } as unknown as ExperimentSnapshotWorkerProxy)
    const wrapper = mountView(EvalsDataset, {
      data: [],
      modelsInfo: {},
      columns: { inputs: [], outputs: [], refs: [], scores: [], metadata: [] },
      datasetId: 'd1',
    })
    await flushPromises()
    await setupFunction(wrapper, 'filtersChange')(['scores.accuracy > 0.5'])
    await nextTick()

    wrapper.unmount()
    evalsStore.resetProvider()
    await vi.advanceTimersByTimeAsync(1_000)

    expect(averageScores).toHaveBeenCalledTimes(1)
    expect(wrapper.emitted('filter-change')).toBeUndefined()
    expect(toastAdd).not.toHaveBeenCalled()
  })
})

describe('a read that ends after its view closed', () => {
  function deferred<T>() {
    let resolve!: (value: T) => void
    const promise = new Promise<T>((done) => (resolve = done))
    return { promise, resolve }
  }

  function setProvider(provider: object) {
    useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  }

  const datasetProvider = (pages: ReturnType<typeof deferred<EvalsInfo[]>>[]) => ({
    getUniqueDatasetsIds: vi.fn(() => Promise.resolve(['d1'])),
    getEvalsColumns: vi.fn(() =>
      Promise.resolve({ inputs: [], outputs: [], refs: [], scores: [], metadata: [] }),
    ),
    resetDatasetPage: vi.fn(() => Promise.resolve()),
    getNextEvalsByDatasetId: vi.fn(() => {
      const page = deferred<EvalsInfo[]>()
      pages.push(page)
      return page.promise
    }),
    getEvalsDatasetAnnotationsSummary: vi.fn(() => Promise.resolve(null)),
    resetEvalsDatasetsRequestParams: vi.fn(() => Promise.resolve()),
  })

  beforeEach(() => {
    setActivePinia(createPinia())
    toastAdd.mockClear()
    uncaughtInView.mockClear()
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('a trace link of the traces table opens no trace dialog', async () => {
    const spans = deferred<TraceSpan[]>()
    setProvider({
      getTraceSpans: vi.fn(() => spans.promise),
      buildSpanTree: vi.fn(() => Promise.resolve([])),
    })
    const wrapper = mountView(TracesTable, { data: [], selectedColumns: [], artifactId: 'm1' })
    const read = setupFunction(wrapper, 'showTrace')('t1')
    wrapper.unmount()
    spans.resolve([makeSpan('s1')])
    await read

    expect(useEvalsStore().selectedTrace).toBeNull()
  })

  it('an eval link of the traces table opens no eval dialog', async () => {
    const evalData = deferred<EvalsInfo>()
    setProvider({ getEvalById: vi.fn(() => evalData.promise) })
    const wrapper = mountView(TracesTable, { data: [], selectedColumns: [], artifactId: 'm1' })
    const read = setupFunction(wrapper, 'showEval')('e1', ['e1', 'e2'])
    wrapper.unmount()
    evalData.resolve(evalRow)
    await read

    expect(useEvalsStore().currentEvalData).toBeNull()
    expect(useEvalsStore().evalsIdsList).toEqual([])
  })

  it('the trace button of a closed eval dialog opens no trace dialog', async () => {
    const spans = deferred<TraceSpan[]>()
    setProvider({
      getEvalAnnotations: vi.fn(() => Promise.resolve([])),
      getTraceId: vi.fn(() => Promise.resolve('t1')),
      getTraceSpans: vi.fn(() => spans.promise),
      buildSpanTree: vi.fn(() => Promise.resolve([])),
    })
    useEvalsStore().setCurrentEvalData([evalRow])
    const wrapper = mountView(TracesModel, { id: 'm1', name: 'model' })
    await flushPromises()
    const read = setupFunction(wrapper, 'showSpans')()
    wrapper.unmount()
    spans.resolve([makeSpan('s1')])
    await read

    expect(useEvalsStore().selectedTrace).toBeNull()
  })

  it('an eval dialog closed while the next eval loads stays closed', async () => {
    const evalData = deferred<EvalsInfo>()
    setProvider({ getEvalById: vi.fn(() => evalData.promise) })
    const evalsStore = useEvalsStore()
    evalsStore.setCurrentEvalData([evalRow])
    const wrapper = mountView(TracesDialog, { modelsInfo: {} })
    const read = setupFunction(wrapper, 'onCurrentEvalIdUpdate')('e2')
    evalsStore.resetCurrentEvalData()
    evalData.resolve({ ...evalRow, id: 'e2' })
    await read

    expect(evalsStore.currentEvalData).toBeNull()
  })

  it('the evals list leaves the loading flag of the next view alone', async () => {
    const pages: ReturnType<typeof deferred<EvalsInfo[]>>[] = []
    setProvider(datasetProvider(pages))
    const wrapper = mountView(EvalsDatasetsList, { modelsInfo: {}, loaderHeight: '10px' })
    await flushPromises()
    expect(pages).toHaveLength(1)
    wrapper.unmount()
    // The next experiment's list is loading already.
    useEvalsStore().setLoading(true)
    pages[0]!.resolve([evalRow])
    await flushPromises()

    expect(useEvalsStore().loading).toBe(true)
    expect(useEvalsStore().datasets).toBeNull()
  })

  it('the evals list reloads with the new sort when it changed while a page was loading', async () => {
    const pages: ReturnType<typeof deferred<EvalsInfo[]>>[] = []
    const provider = datasetProvider(pages)
    setProvider(provider)
    const wrapper = mountView(EvalsDatasetsList, { modelsInfo: {}, loaderHeight: '10px' })
    await flushPromises()
    pages[0]!.resolve([evalRow])
    await flushPromises()

    const nextPage = setupFunction(wrapper, 'getNextPage')('d1')
    await flushPromises()
    await setupFunction(wrapper, 'onSort')('d1', { sortField: 'created_at', sortOrder: 'asc' })
    pages[1]!.resolve([{ ...evalRow, id: 'old-sort' }])
    await nextPage
    await flushPromises()

    expect(provider.getNextEvalsByDatasetId).toHaveBeenCalledTimes(3)
    expect(provider.getNextEvalsByDatasetId).toHaveBeenLastCalledWith(
      expect.objectContaining({ sort_by: 'created_at', order: 'asc' }),
    )
    pages[2]!.resolve([{ ...evalRow, id: 'new-sort' }])
    await flushPromises()

    expect(useEvalsStore().datasets?.[0]?.data.map((row) => row.id)).toEqual(['new-sort'])
    expect(useEvalsStore().loading).toBe(false)
    expect(toastAdd).not.toHaveBeenCalled()
  })
})
