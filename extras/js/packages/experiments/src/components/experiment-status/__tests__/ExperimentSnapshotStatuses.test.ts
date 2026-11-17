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

describe('ExperimentSnapshot status notices', () => {
  it('reads the statuses once, after the catalogs, and shows one line per affected experiment', async () => {
    setActivePinia(createPinia())
    const source = new FakeBucketSource({ a: { loss: points(0, 9) }, b: { loss: points(0, 9) } })
    source.skippedRows.b = 4
    const provider = Object.assign(source, {
      getStaticParamsList: vi.fn(async () => []),
    }) as unknown as ExperimentSnapshotProvider

    const wrapper = mount(ExperimentSnapshot, {
      props: {
        provider,
        modelsIds: ['a', 'b'],
        modelsInfo: { a: { name: 'Run A', color: '#000' }, b: { name: 'Run B', color: '#111' } },
        theme: 'light',
      },
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
