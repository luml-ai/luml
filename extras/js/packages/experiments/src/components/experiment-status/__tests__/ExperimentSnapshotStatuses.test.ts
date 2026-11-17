import { describe, expect, it, vi } from 'vitest'
import { mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ExperimentSnapshot from '@/ExperimentSnapshot.vue'
import { useEvalsStore } from '@/store/evals'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import {
  FakeBucketSource,
  points,
} from '@/components/dynamic-metrics/__tests__/helpers/fakeBucketSource'
import { settle } from '@/components/dynamic-metrics/__tests__/helpers/plotlyMock'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

const MODELS_INFO = {
  a: { name: 'Run A', color: '#000' },
  b: { name: 'Run B', color: '#111' },
  c: { name: 'Run C', color: '#222' },
}

function snapshotProvider(source: FakeBucketSource): ExperimentSnapshotProvider {
  return Object.assign(source, {
    getStaticParamsList: vi.fn(async () => []),
  }) as unknown as ExperimentSnapshotProvider
}

function mountSnapshot(provider: ExperimentSnapshotProvider, modelsIds: string[]) {
  return mount(ExperimentSnapshot, {
    props: { provider, modelsIds, modelsInfo: MODELS_INFO, theme: 'light' },
    global: {
      plugins: [[PrimeVue, { unstyled: true }]],
      stubs: {
        DynamicMetricsItem: true,
        EvalsDatasetsList: true,
        TracesWrapper: true,
        TracesDialog: true,
        TraceDialog: true,
        StaticParametersMultiple: true,
      },
    },
  })
}

describe('ExperimentSnapshot status notices', () => {
  it('reads the statuses once, after the catalogs, and shows one line per affected experiment', async () => {
    setActivePinia(createPinia())
    const source = new FakeBucketSource({ a: { loss: points(0, 9) }, b: { loss: points(0, 9) } })
    source.skippedRows.b = 4

    const wrapper = mountSnapshot(snapshotProvider(source), ['a', 'b'])
    await settle()

    expect(useEvalsStore().metricBucketStore).not.toBeNull()
    expect(source.getExperimentStatuses).toHaveBeenCalledOnce()
    expect(source.getMetricCatalogs.mock.invocationCallOrder[0]).toBeLessThan(
      source.getExperimentStatuses.mock.invocationCallOrder.at(-1) ?? 0,
    )
    const notices = wrapper.findAll('[data-testid="experiment-status-notice"]')
    expect(notices.map((notice) => notice.text())).toEqual([
      'Run B: 4 metric points were skipped because their steps are not integers.',
    ])
    wrapper.unmount()
  })
})

describe('ExperimentSnapshot metric store lifetime', () => {
  it('frees the store and the provider on unmount', async () => {
    setActivePinia(createPinia())
    const source = new FakeBucketSource({ a: { loss: points(0, 9) } })
    const wrapper = mountSnapshot(snapshotProvider(source), ['a'])
    await settle()
    const store = useEvalsStore().metricBucketStore

    wrapper.unmount()

    expect(store?.disposed).toBe(true)
    expect(useEvalsStore().metricBucketStore).toBeNull()
    expect(() => useEvalsStore().getProvider).toThrow('Provider not found')
  })

  it('reads the catalogs again when the same provider is opened for other experiments', async () => {
    setActivePinia(createPinia())
    const source = new FakeBucketSource({
      a: { loss: points(0, 9) },
      b: { loss: points(0, 9) },
      c: { loss: points(0, 9) },
    })
    const provider = snapshotProvider(source)
    const first = mountSnapshot(provider, ['a', 'c'])
    await settle()
    first.unmount()

    mountSnapshot(provider, ['a', 'b'])
    await settle()

    const store = useEvalsStore().metricBucketStore
    expect(store?.disposed).toBe(false)
    expect(store?.modelIds).toEqual(['a', 'b'])
    expect(source.catalogCalls.at(-1)).toEqual({ modelIds: ['b'] })
  })
})
