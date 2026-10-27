import { flushPromises, mount } from '@vue/test-utils'
import { defineComponent, h } from 'vue'
import { createMemoryHistory, createRouter, RouterView } from 'vue-router'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import ExperimentDetailsPage from '../ExperimentDetailsPage.vue'

const harness = vi.hoisted(() => ({
  fetchExperiment: vi.fn(),
  resetExperiment: vi.fn(),
  resetProvider: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('@/store/experiment', () => ({
  useExperimentStore: () => ({
    experiment: null,
    fetchExperiment: harness.fetchExperiment,
    resetExperiment: harness.resetExperiment,
  }),
}))
vi.mock('@/store/theme', () => ({
  useThemeStore: () => ({ theme: 'light' }),
}))
vi.mock('@/hooks/useExperimentProvider', async () => {
  const { ref } = await import('vue')
  return {
    useExperimentProvider: () => ({
      provider: ref(null),
      createProvider: vi.fn(),
      resetProvider: harness.resetProvider,
    }),
  }
})
vi.mock('primevue', () => ({
  useToast: () => ({ add: harness.toastAdd }),
  Skeleton: { render: () => null },
}))
vi.mock('@luml/experiments', () => ({
  useEvalsStore: () => ({ resetProvider: vi.fn() }),
  useAnnotationsStore: () => ({ allowEdit: vi.fn() }),
  provideTheme: vi.fn(),
  TracesDialog: { render: () => null },
  TraceDialog: { render: () => null },
}))
vi.mock('@/components/experiments/details/DetailsBreadcrumbs.vue', () => ({
  default: { render: () => null },
}))
vi.mock('@/components/experiments/details/DetailsTabs.vue', () => ({
  default: { render: () => null },
}))
vi.mock('@/components/experiments/details/RefreshButton.vue', () => ({
  default: { render: () => null },
}))

describe('ExperimentDetailsPage', () => {
  let wrapper: ReturnType<typeof mount> | undefined

  async function mountPage(path = '/details/first/overview', routed = true) {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: [
        { path: '/details/:experimentId?/:tab?', component: ExperimentDetailsPage },
        { path: '/home', component: { render: () => h('div', 'home') } },
      ],
    })
    await router.push(path)
    await router.isReady()
    wrapper = mount(
      routed ? defineComponent({ render: () => h(RouterView) }) : ExperimentDetailsPage,
      {
        global: { plugins: [router] },
      },
    )
    await flushPromises()
    return router
  }

  beforeEach(() => {
    vi.clearAllMocks()
    harness.fetchExperiment
      .mockReset()
      .mockImplementation((id: string | undefined) =>
        id ? Promise.resolve() : Promise.reject(new Error('Experiment not found')),
      )
  })

  afterEach(() => wrapper?.unmount())

  it('loads the initial experiment and reloads when its route id changes', async () => {
    const router = await mountPage()
    expect(harness.fetchExperiment).toHaveBeenCalledExactlyOnceWith('first')

    await router.push('/details/second/overview')
    await flushPromises()

    expect(harness.fetchExperiment).toHaveBeenCalledTimes(2)
    expect(harness.fetchExperiment).toHaveBeenLastCalledWith('second')
    expect(harness.toastAdd).not.toHaveBeenCalled()
  })

  it('does not reload when switching tabs for the same experiment', async () => {
    const router = await mountPage()

    await router.push('/details/first/metrics')
    await flushPromises()

    expect(harness.fetchExperiment).toHaveBeenCalledExactlyOnceWith('first')
  })

  it('does not fetch a missing id or show an error when leaving the details page', async () => {
    const router = await mountPage()

    await router.push('/home')
    await flushPromises()

    expect(wrapper?.text()).toBe('home')
    expect(harness.fetchExperiment).toHaveBeenCalledExactlyOnceWith('first')
    expect(harness.toastAdd).not.toHaveBeenCalled()
    expect(harness.resetExperiment).toHaveBeenCalledOnce()
    expect(harness.resetProvider).toHaveBeenCalledOnce()
  })

  it('does not fetch if the route loses its experiment id before the page unmounts', async () => {
    const router = await mountPage('/details/first/overview', false)

    await router.push('/home')
    await flushPromises()

    expect(harness.fetchExperiment).toHaveBeenCalledExactlyOnceWith('first')
    expect(harness.toastAdd).not.toHaveBeenCalled()
  })

  it.each(['/details', '/home'])('does not fetch a missing initial id at %s', async (path) => {
    await mountPage(path, false)

    expect(harness.fetchExperiment).not.toHaveBeenCalled()
    expect(harness.toastAdd).not.toHaveBeenCalled()
  })

  it('stops fetching after unmount', async () => {
    const router = await mountPage()
    wrapper?.unmount()
    wrapper = undefined

    await router.push('/details/second/overview')
    await flushPromises()

    expect(harness.fetchExperiment).toHaveBeenCalledExactlyOnceWith('first')
  })

  it('reports failures for valid ids and retries when the experiment changes', async () => {
    harness.fetchExperiment.mockRejectedValueOnce(new Error('Load failed'))
    const router = await mountPage()
    expect(harness.toastAdd).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'Load failed' }),
    )

    await router.push('/details/second/overview')
    await flushPromises()

    expect(harness.fetchExperiment).toHaveBeenLastCalledWith('second')
    expect(harness.toastAdd).toHaveBeenCalledOnce()
  })
})
