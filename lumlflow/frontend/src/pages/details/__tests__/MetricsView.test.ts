import { mount } from '@vue/test-utils'
import { defineComponent, h, reactive } from 'vue'
import { describe, expect, it, vi } from 'vitest'
import MetricsView from '../MetricsView.vue'

const harness = vi.hoisted(() => ({
  metrics: null as unknown as {
    loading: boolean
    catalogs: { errors: Map<string, unknown> } | null
    metricsNames: string[]
    statuses: { modelId: string }[]
  },
}))

vi.mock('@/store/experiment', () => ({
  useExperimentStore: () => ({
    experiment: { id: 'e1', name: 'Run 1', dynamic_params: { stale_key: 1 } },
  }),
}))
vi.mock('@luml/experiments', () => ({
  useDynamicMetricsStore: () => harness.metrics,
  DynamicMetrics: defineComponent({ render: () => h('div', { 'data-testid': 'charts' }) }),
  ExperimentStatusNotices: defineComponent({
    props: { statuses: { type: Array, required: true }, modelsInfo: Object },
    render() {
      return h('div', { 'data-testid': 'notices' }, String(this.statuses.length))
    },
  }),
}))

function mountView(state: Partial<typeof harness.metrics>) {
  harness.metrics = reactive({
    loading: false,
    catalogs: { errors: new Map() },
    metricsNames: [],
    statuses: [],
    ...state,
  })
  return mount(MetricsView)
}

describe('MetricsView', () => {
  it('shows the status notices of the shared viewer next to the charts', () => {
    const view = mountView({ metricsNames: ['loss'], statuses: [{ modelId: 'e1' }] })

    expect(view.get('[data-testid="notices"]').text()).toBe('1')
    expect(view.find('[data-testid="charts"]').exists()).toBe(true)
    expect(view.text()).not.toContain('No metrics found')
  })

  it('says there are no metrics from the catalog, not from dynamic_params', () => {
    expect(mountView({ metricsNames: [] }).text()).toContain('No metrics found in this experiment')
    expect(mountView({ metricsNames: [], loading: true }).text()).not.toContain('No metrics found')
    expect(mountView({ metricsNames: [], catalogs: null }).text()).not.toContain('No metrics found')
  })

  it('does not say there are no metrics when the catalog could not be read', () => {
    const failed = { errors: new Map([['e1', { code: 'read-failed', message: 'x' }]]) }
    expect(mountView({ metricsNames: [], catalogs: failed }).text()).not.toContain(
      'No metrics found',
    )
  })
})
