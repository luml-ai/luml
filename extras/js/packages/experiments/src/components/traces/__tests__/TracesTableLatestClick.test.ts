import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import type { EvalsInfo, ExperimentSnapshotProvider, TraceSpan } from '@/interfaces/interfaces'
import { useEvalsStore } from '@/store/evals'
import TracesTable from '../TracesTable.vue'

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

function span(traceId: string) {
  return {
    trace_id: traceId,
    span_id: `${traceId}-root`,
    start_time_unix_nano: 1,
    end_time_unix_nano: 2,
  } as unknown as TraceSpan
}

function setupProvider() {
  const spanReads = new Map<string, ReturnType<typeof deferred<TraceSpan[]>>>()
  const evalReads = new Map<string, ReturnType<typeof deferred<EvalsInfo>>>()
  const provider = {
    getTraceSpans: vi.fn((_modelId: string, traceId: string) => {
      const read = deferred<TraceSpan[]>()
      spanReads.set(traceId, read)
      return read.promise
    }),
    buildSpanTree: vi.fn(async (spans: TraceSpan[]) => spans),
    getEvalById: vi.fn((_artifactId: string, evalId: string) => {
      const read = deferred<EvalsInfo>()
      evalReads.set(evalId, read)
      return read.promise
    }),
  }
  useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  return { provider, spanReads, evalReads }
}

function mountTable() {
  const wrapper = mount(TracesTable, {
    shallow: true,
    props: { data: [], artifactId: 'model-1', selectedColumns: [] },
    global: { plugins: [[PrimeVue, { unstyled: true }]] },
  })
  return wrapper.vm as unknown as {
    showTrace: (traceId: string) => Promise<void>
    showEval: (evalId: string, evalsIds: string[]) => Promise<void>
  }
}

describe('TracesTable rows clicked one after the other', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.restoreAllMocks()
  })

  it('keeps the trace clicked last when the earlier trace answers after it', async () => {
    const { spanReads } = setupProvider()
    const vm = mountTable()

    const first = vm.showTrace('trace-0')
    const second = vm.showTrace('trace-1')
    spanReads.get('trace-1')!.resolve([span('trace-1')])
    await second
    expect(useEvalsStore().selectedTrace?.traceId).toBe('trace-1')

    spanReads.get('trace-0')!.resolve([span('trace-0')])
    await first
    await flushPromises()
    expect(useEvalsStore().selectedTrace?.traceId).toBe('trace-1')
  })

  it('keeps the eval clicked last when the earlier eval answers after it', async () => {
    const { evalReads } = setupProvider()
    const vm = mountTable()

    const first = vm.showEval('eval-0', ['eval-0'])
    const second = vm.showEval('eval-1', ['eval-1', 'eval-2'])
    evalReads.get('eval-1')!.resolve({ id: 'eval-1', dataset_id: 'd1' } as EvalsInfo)
    await second

    evalReads.get('eval-0')!.resolve({ id: 'eval-0', dataset_id: 'd1' } as EvalsInfo)
    await first
    await flushPromises()
    expect(useEvalsStore().currentEvalId).toBe('eval-1')
    expect(useEvalsStore().evalsIdsList).toEqual(['eval-1', 'eval-2'])
  })

  it('keeps the eval clicked last when an earlier trace answers after it', async () => {
    const { spanReads, evalReads } = setupProvider()
    const vm = mountTable()

    const trace = vm.showTrace('trace-0')
    const evalRead = vm.showEval('eval-1', ['eval-1'])
    evalReads.get('eval-1')!.resolve({ id: 'eval-1', dataset_id: 'd1' } as EvalsInfo)
    await evalRead

    spanReads.get('trace-0')!.resolve([span('trace-0')])
    await trace
    await flushPromises()
    expect(useEvalsStore().currentEvalId).toBe('eval-1')
    expect(useEvalsStore().selectedTrace).toBeNull()
  })

  it('keeps the trace clicked last when an earlier eval answers after it', async () => {
    const { spanReads, evalReads } = setupProvider()
    const vm = mountTable()

    const evalRead = vm.showEval('eval-0', ['eval-0'])
    const trace = vm.showTrace('trace-1')
    spanReads.get('trace-1')!.resolve([span('trace-1')])
    await trace

    evalReads.get('eval-0')!.resolve({ id: 'eval-0', dataset_id: 'd1' } as EvalsInfo)
    await evalRead
    await flushPromises()
    expect(useEvalsStore().selectedTrace?.traceId).toBe('trace-1')
    expect(useEvalsStore().currentEvalId).toBe('')
  })
})
