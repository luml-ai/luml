import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick, reactive } from 'vue'
import CompareView from '../CompareView.vue'

enableAutoUnmount(afterEach)

const harness = vi.hoisted(() => ({
  route: { query: { artifacts: [] as string[] } },
  getArtifact: vi.fn(),
  resetExperimentSnapshotProvider: vi.fn(),
  init: vi.fn(),
  cancel: vi.fn(),
  provider: null as unknown,
}))

vi.mock('@luml/experiments', async () => ({
  ComparisonModelsList: (
    await import('../../../../../../extras/js/packages/experiments/src/components/comparison/ComparisonModelsList.vue')
  ).default,
  ComparisonHeader: { template: '<div />' },
  ExperimentSnapshot: { template: '<div class="snapshot" />' },
}))

vi.mock('vue-router', () => ({ useRoute: () => harness.route }))
vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({
    getArtifact: harness.getArtifact,
    resetExperimentSnapshotProvider: harness.resetExperimentSnapshotProvider,
    get experimentSnapshotProvider() {
      return harness.provider
    },
  }),
}))
vi.mock('@/stores/theme', () => ({
  useThemeStore: () => ({ getCurrentTheme: 'light' }),
}))
vi.mock('@/hooks/useExperimentSnapshotsDatabaseProvider', () => ({
  useExperimentSnapshotsDatabaseProvider: () => ({ init: harness.init, cancel: harness.cancel }),
}))
vi.mock('@/helpers/helpers', () => ({
  getArtifactColorByIndex: (index: number) => ['red', 'blue'][index],
}))

describe('CompareView model list', () => {
  beforeEach(() => {
    harness.route.query.artifacts = []
    harness.getArtifact.mockReset()
    harness.init.mockReset().mockResolvedValue(undefined)
  })

  it('renders artifact names and colors without passing unused attributes to the list', async () => {
    harness.route.query.artifacts = ['a', 'b']
    harness.getArtifact.mockImplementation(async (id: string) => ({
      id,
      name: id === 'a' ? 'Model A' : 'Model B',
    }))
    const wrapper = mount(CompareView)

    await flushPromises()

    const list = wrapper.get('.models')
    expect(list.findAll('.model').map((model) => model.text())).toEqual(['Model A', 'Model B'])
    expect(list.findAll('.model-circle').map((circle) => circle.attributes('style'))).toEqual([
      'background-color: red;',
      'background-color: blue;',
    ])
    expect(list.attributes()).not.toHaveProperty('models-ids')
    expect(list.attributes()).not.toHaveProperty('models-list')
  })

  it.each(['no selection', 'failed load'])(
    'renders an empty list without unused attributes for %s',
    async (scenario) => {
      if (scenario === 'failed load') {
        harness.route.query.artifacts = ['missing']
        harness.getArtifact.mockRejectedValue(new Error('Artifact not found'))
      }
      const wrapper = mount(CompareView)

      await flushPromises()

      const list = wrapper.get('.models')
      expect(list.findAll('.model')).toHaveLength(0)
      expect(list.attributes()).not.toHaveProperty('models-ids')
      expect(list.attributes()).not.toHaveProperty('models-list')
    },
  )
})

describe('CompareView when the set changes before the previous one is loaded', () => {
  beforeEach(() => {
    harness.route = reactive({ query: { artifacts: ['a'] } })
    harness.getArtifact.mockReset()
    harness.init.mockReset().mockResolvedValue(undefined)
    harness.cancel.mockReset()
    harness.resetExperimentSnapshotProvider.mockReset()
    harness.provider = null
  })

  afterEach(() => {
    harness.route = { query: { artifacts: [] } }
    harness.provider = null
    vi.restoreAllMocks()
  })

  it('shows and opens only the latest set when the older one answers last', async () => {
    let answerA!: (artifact: { id: string; name: string }) => void
    harness.getArtifact.mockImplementation((id: string) =>
      id === 'a'
        ? new Promise((resolve) => (answerA = resolve))
        : Promise.resolve({ id, name: 'Model B' }),
    )
    const wrapper = mount(CompareView)
    await flushPromises()

    harness.route.query.artifacts = ['b']
    await nextTick()
    await flushPromises()
    answerA({ id: 'a', name: 'Model A' })
    await flushPromises()

    expect(wrapper.findAll('.model').map((model) => model.text())).toEqual(['Model B'])
    expect(harness.init).toHaveBeenCalledExactlyOnceWith([{ id: 'b', name: 'Model B' }])
  })

  it('shows no provider of the older set when it opens during the newer fetch and the newer open fails', async () => {
    vi.spyOn(console, 'error').mockImplementation(() => {})
    // Like the real hook: an init sets its provider when it ends, unless it was cancelled or
    // replaced by a newer init first.
    let current: symbol | null = null
    let finishOld!: () => void
    let answerB!: (artifact: { id: string; name: string }) => void
    harness.cancel.mockImplementation(() => (current = null))
    harness.resetExperimentSnapshotProvider.mockImplementation(() => (harness.provider = null))
    harness.init.mockImplementation((models: { id: string }[]) => {
      const token = Symbol(models[0]?.id)
      current = token
      if (models[0]?.id !== 'a') return Promise.reject(new Error('open failed'))
      return new Promise<void>((resolve) => {
        finishOld = () => {
          if (current === token) harness.provider = { set: 'a' }
          resolve()
        }
      })
    })
    harness.getArtifact.mockImplementation((id: string) =>
      id === 'a'
        ? Promise.resolve({ id, name: 'Model A' })
        : new Promise((resolve) => (answerB = resolve)),
    )
    const wrapper = mount(CompareView)
    await flushPromises()
    expect(harness.init).toHaveBeenCalledOnce()

    harness.route.query.artifacts = ['b']
    await nextTick()
    await flushPromises()
    finishOld()
    await flushPromises()
    answerB({ id: 'b', name: 'Model B' })
    await flushPromises()

    expect(harness.init).toHaveBeenCalledTimes(2)
    expect(harness.provider).toBeNull()
    expect(wrapper.find('.snapshot').exists()).toBe(false)
  })
})
