import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import { describe, expect, it, vi } from 'vitest'
import RefreshButton from '../RefreshButton.vue'
import { ROUTE_NAMES } from '@/router/router.const'

const harness = vi.hoisted(() => ({
  fetchExperiment: vi.fn(async () => undefined),
  refreshMetrics: vi.fn(
    async (): Promise<Map<string, { code: string; message: string }>> => new Map(),
  ),
  toastAdd: vi.fn(),
}))

vi.mock('@/store/experiment', () => ({
  useExperimentStore: () => ({
    experiment: { id: 'exp-1', status: 'active' },
    fetchExperiment: harness.fetchExperiment,
  }),
}))
vi.mock('primevue', async () => {
  const { defineComponent, h } = await import('vue')
  return {
    useToast: () => ({ add: harness.toastAdd }),
    Button: defineComponent({
      emits: ['click'],
      setup(_, { emit }) {
        return () => h('button', { onClick: () => emit('click') })
      },
    }),
  }
})
vi.mock('@luml/experiments', () => ({
  useDynamicMetricsStore: () => ({ refresh: harness.refreshMetrics }),
  useTraceStore: () => ({ refresh: vi.fn() }),
  useEvalsStore: () => ({ refresh: vi.fn() }),
}))

async function mountOnMetricsRoute() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        name: ROUTE_NAMES.EXPERIMENT_METRICS,
        path: '/experiments/:experimentId/metrics',
        component: defineComponent({ render: () => h('div') }),
      },
    ],
  })
  await router.push('/experiments/exp-1/metrics')
  await router.isReady()
  const wrapper = mount(RefreshButton, { global: { plugins: [router] } })
  return wrapper
}

describe('RefreshButton', () => {
  it('re-reads the metric catalogs of this experiment only', async () => {
    const wrapper = await mountOnMetricsRoute()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(harness.fetchExperiment).toHaveBeenCalledWith('exp-1')
    expect(harness.refreshMetrics).toHaveBeenCalledWith(['exp-1'])
    expect(harness.toastAdd).not.toHaveBeenCalled()
  })

  it('reports a catalog refresh that failed', async () => {
    harness.refreshMetrics.mockResolvedValueOnce(
      new Map([['exp-1', { code: 'read-failed', message: 'Server is down' }]]),
    )
    const wrapper = await mountOnMetricsRoute()
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(harness.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Server is down' }),
    )
  })
})
