import { flushPromises, mount } from '@vue/test-utils'
import { createMemoryHistory, createRouter } from 'vue-router'
import { afterEach, expect, it, vi } from 'vitest'
import ExperimentsComparison from '../ExperimentsComparison.vue'
const { getExperiment } = vi.hoisted(() => ({
  getExperiment: vi.fn().mockImplementation((id) => Promise.resolve({ id, name: id })),
}))
vi.mock('@/api/api.service', () => ({ apiService: { getExperiment } }))
vi.mock('@/store/theme', () => ({ useThemeStore: () => ({ theme: 'light' }) }))
vi.mock('primevue', () => ({
  useToast: () => ({ add: vi.fn() }),
  Skeleton: { render: () => null },
}))
vi.mock('@luml/experiments', () => ({
  useAnnotationsStore: () => ({ allowEdit: vi.fn() }),
  ComparisonHeader: { render: () => null },
  ComparisonModelsList: { render: () => null },
  ExperimentSnapshot: { render: () => null },
}))
vi.mock('@/hooks/useExperimentProvider', () => ({
  useExperimentProvider: () => ({
    provider: null,
    createProvider: vi.fn(),
    resetProvider: vi.fn(),
  }),
}))
afterEach(() => vi.clearAllMocks())
it.each([
  ['?ids=one', ['one']],
  ['?ids=one&ids=two', ['one', 'two']],
])('loads comparison ids %s', async (query, ids) => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: ExperimentsComparison }],
  })
  await router.push('/' + query)
  const wrapper = mount(ExperimentsComparison, { global: { plugins: [router] } })
  await flushPromises()
  expect(getExperiment.mock.calls.map(([id]) => id)).toEqual(ids)
  wrapper.unmount()
})
it('shows a recoverable error when no ids are provided', async () => {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [{ path: '/', component: ExperimentsComparison }],
  })
  await router.push('/')
  const wrapper = mount(ExperimentsComparison, { global: { plugins: [router] } })
  await flushPromises()
  expect(wrapper.text()).toContain('Experiments IDs are required')
  expect(getExperiment).not.toHaveBeenCalled()
  wrapper.unmount()
})
