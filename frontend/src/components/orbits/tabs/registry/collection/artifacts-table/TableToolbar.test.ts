import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import type { ArtifactListed } from '@/lib/api/artifacts/interfaces'
import TableToolbar from './TableToolbar.vue'

const mocks = vi.hoisted(() => ({ toast: vi.fn(), downloadArtifact: vi.fn() }))

vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => ({}) }))
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ currentCollection: { type: 'model' } }),
}))
vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({ downloadArtifact: mocks.downloadArtifact }),
}))
vi.mock('vue-router', () => ({ useRouter: () => ({ push: vi.fn() }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useConfirm: () => ({ require: vi.fn() }),
  useToast: () => ({ add: mocks.toast }),
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

describe('artifact download', () => {
  it('reports a failed download as a download error', async () => {
    mocks.downloadArtifact.mockRejectedValueOnce(new Error('Failed to download artifact'))
    const wrapper = shallowMount(TableToolbar, {
      props: {
        selectedArtifacts: [
          { id: 'a1', file_name: 'model.fnnx', status: 'uploaded' },
        ] as ArtifactListed[],
        metrics: [],
      },
      global: {
        directives: { tooltip: () => {} },
        stubs: {
          Button: {
            emits: ['click'],
            template: '<button @click="$emit(\'click\')"></button>',
          },
        },
      },
    })
    await wrapper.get('[aria-label="Download"]').trigger('click')
    await flushPromises()

    expect(mocks.downloadArtifact).toHaveBeenCalledExactlyOnceWith('a1', 'model.fnnx')
    expect(mocks.toast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'Failed to download artifact' }),
    )
    expect(wrapper.emitted('clearSelectedArtifacts')).toHaveLength(1)
    wrapper.unmount()
  })
})
