import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import type { EvalsInfo, ExperimentSnapshotProvider, TraceSpan } from '@/interfaces/interfaces'
import { useEvalsStore } from '@/store/evals'
import TracesModel from '../TracesModel.vue'

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

function setupProvider() {
  const spanReads = new Map<string, ReturnType<typeof deferred<TraceSpan[]>>>()
  const provider = {
    getTraceId: vi.fn(async ({ modelId }: { modelId: string }) => `trace-${modelId}`),
    getTraceSpans: vi.fn((modelId: string) => {
      const read = deferred<TraceSpan[]>()
      spanReads.set(modelId, read)
      return read.promise
    }),
    buildSpanTree: vi.fn(async (spans: TraceSpan[]) => spans),
    getEvalAnnotations: vi.fn(async () => []),
  }
  const store = useEvalsStore()
  store.setProvider(provider as unknown as ExperimentSnapshotProvider)
  store.setCurrentEvalData([
    { id: 'e1', dataset_id: 'd1', modelId: 'm1', scores: {} },
    { id: 'e1', dataset_id: 'd1', modelId: 'm2', scores: {} },
  ] as unknown as EvalsInfo[])
  return { spanReads }
}

function mountModel(id: string) {
  const wrapper = mount(TracesModel, {
    shallow: true,
    props: { id, name: id },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  })
  return wrapper.vm as unknown as { showSpans: () => Promise<void> }
}

describe('TracesModel trace asked for in two models of a comparison', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps the trace of the model clicked last', async () => {
    const { spanReads } = setupProvider()
    const first = mountModel('m1')
    const second = mountModel('m2')
    await flushPromises()

    const firstClick = first.showSpans()
    const secondClick = second.showSpans()
    await flushPromises()
    spanReads.get('m2')!.resolve([])
    await secondClick
    spanReads.get('m1')!.resolve([])
    await firstClick
    await flushPromises()

    expect(useEvalsStore().selectedTrace?.artifactId).toBe('m2')
  })
})
