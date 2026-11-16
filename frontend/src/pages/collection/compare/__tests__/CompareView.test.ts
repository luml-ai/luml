import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CompareView from '../CompareView.vue'

enableAutoUnmount(afterEach)

const harness = vi.hoisted(() => ({
  route: { query: { artifacts: [] as string[] } },
  getArtifact: vi.fn(),
  resetExperimentSnapshotProvider: vi.fn(),
  init: vi.fn(),
}))

vi.mock('@luml/experiments', async () => ({
  ComparisonModelsList: (
    await import('../../../../../../extras/js/packages/experiments/src/components/comparison/ComparisonModelsList.vue')
  ).default,
  ComparisonHeader: { template: '<div />' },
  ExperimentSnapshot: { template: '<div />' },
}))

vi.mock('vue-router', () => ({ useRoute: () => harness.route }))
vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({
    getArtifact: harness.getArtifact,
    resetExperimentSnapshotProvider: harness.resetExperimentSnapshotProvider,
    experimentSnapshotProvider: null,
  }),
}))
vi.mock('@/stores/theme', () => ({
  useThemeStore: () => ({ getCurrentTheme: 'light' }),
}))
vi.mock('@/hooks/useExperimentSnapshotsDatabaseProvider', () => ({
  useExperimentSnapshotsDatabaseProvider: () => ({ init: harness.init }),
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
