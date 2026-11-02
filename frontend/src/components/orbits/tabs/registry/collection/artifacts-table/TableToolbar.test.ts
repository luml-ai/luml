import { shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { ArtifactListed } from '@/lib/api/artifacts/interfaces'
import TableToolbar from './TableToolbar.vue'

vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => ({}) }))
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ currentCollection: { type: 'model' } }),
}))
vi.mock('@/stores/artifacts', () => ({ useArtifactsStore: () => ({}) }))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useConfirm: () => ({ require: vi.fn() }),
  useToast: () => ({ add: vi.fn() }),
}))

describe('artifact comparison selection', () => {
  it.each([
    [[], true],
    [[{ status: 'uploaded', has_experiment_snapshot: true }], true],
    [
      [
        { status: 'uploaded', has_experiment_snapshot: true },
        { status: 'uploaded', has_experiment_snapshot: true },
      ],
      false,
    ],
    [
      [
        { status: 'uploaded', has_experiment_snapshot: true },
        { status: 'uploaded', has_experiment_snapshot: false },
      ],
      true,
    ],
    [
      [
        { status: 'uploaded', has_experiment_snapshot: true },
        { status: 'pending_upload', has_experiment_snapshot: true },
      ],
      true,
    ],
    [[{ status: 'uploaded' }, { status: 'uploaded', has_experiment_snapshot: true }], true],
  ])('sets compare disabled=%s for selection %s', (selection, disabled) => {
    const wrapper = shallowMount(TableToolbar, {
      props: { selectedArtifacts: selection as ArtifactListed[], metrics: [] },
      global: {
        directives: { tooltip: () => {} },
        stubs: {
          Button: {
            props: ['disabled'],
            template: '<button :disabled="disabled"><slot /></button>',
          },
        },
      },
    })
    const compare = wrapper.find('[aria-label="Compare"]')
    expect(compare.exists()).toBe(true)
    expect(compare.attributes('disabled') !== undefined).toBe(disabled)
    wrapper.unmount()
  })
})
