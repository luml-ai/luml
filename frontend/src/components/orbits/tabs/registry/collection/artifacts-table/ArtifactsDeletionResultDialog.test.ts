import { flushPromises, mount, RouterLinkStub } from '@vue/test-utils'
import type { ArtifactDeleteFailure, ArtifactDeleteReason } from '@/lib/api/artifacts/interfaces'
import type { DeleteArtifactsResult } from '@/stores/artifacts/artifacts.interface'
import { DeploymentStatusEnum } from '@/lib/api/deployments/interfaces'
import { defineComponent, nextTick, reactive } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import ArtifactsDeletionResultDialog from './ArtifactsDeletionResultDialog.vue'

const toastAdd = vi.fn()
const deletionState = reactive<{ deletionResult: DeleteArtifactsResult | null }>({
  deletionResult: null,
})
const artifactsStore = {
  get deletionResult(): DeleteArtifactsResult | null {
    return deletionState.deletionResult
  },
  forceDeleteArtifacts: vi.fn(),
  setDeletionResult: vi.fn((result: DeleteArtifactsResult | null) => {
    deletionState.deletionResult = result
  }),
  resetDeletionResult: vi.fn(() => {
    deletionState.deletionResult = null
  }),
}

vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => artifactsStore,
}))

vi.mock('vue-router', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return {
    ...actual,
    useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
  }
})

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: toastAdd }) }
})

const DialogStub = defineComponent({
  props: {
    visible: Boolean,
  },
  template:
    '<section v-if="visible" role="dialog"><h1><slot name="header" /></h1><slot /><footer><slot name="footer" /></footer></section>',
})

const ButtonStub = defineComponent({
  props: {
    disabled: Boolean,
  },
  emits: ['click'],
  template: '<button :disabled="disabled" @click="$emit(\'click\')"><slot /></button>',
})

const ForceDeleteConfirmDialogStub = defineComponent({
  props: {
    visible: Boolean,
  },
  emits: ['update:visible', 'confirm'],
  template:
    '<div v-if="visible" data-testid="force-confirm"><button @click="$emit(\'confirm\')">Confirm force</button></div>',
})

function failure(
  artifactId: string,
  reason: ArtifactDeleteReason,
  overrides: Partial<ArtifactDeleteFailure> = {},
): ArtifactDeleteFailure {
  return {
    artifact_id: artifactId,
    name: artifactId,
    reason,
    deployments: [],
    tracks: [],
    ...overrides,
  }
}

function mountDialog(failures: ArtifactDeleteFailure[]) {
  deletionState.deletionResult = { deleted: [], failed: failures }
  return mount(ArtifactsDeletionResultDialog, {
    global: {
      stubs: {
        Dialog: DialogStub,
        Button: ButtonStub,
        RouterLink: RouterLinkStub,
        ForceDeleteConfirmDialog: ForceDeleteConfirmDialogStub,
      },
    },
  })
}

function normalizedText(wrapper: ReturnType<typeof mountDialog>): string {
  return wrapper.text().replace(/\s+/g, ' ').trim()
}

function buttonByName(wrapper: ReturnType<typeof mountDialog>, name: string) {
  return wrapper.findAll('button').find((button) => button.text() === name)
}

describe('ArtifactsDeletionResultDialog', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    deletionState.deletionResult = null
  })

  it('renders each reason, external blocker links, and count-specific titles', async () => {
    const wrapper = mountDialog([
      failure('artifact-a', 'deployments', {
        name: 'A',
        deployments: [
          { id: 'deployment-1', name: 'api', status: DeploymentStatusEnum.active },
          { id: 'deployment-2', name: 'old', status: DeploymentStatusEnum.failed },
        ],
      }),
      failure('artifact-b', 'tracks', {
        name: 'B',
        tracks: [{ id: 'track-1', name: 'release' }],
      }),
      failure('artifact-c', 'storage_error', { name: 'C' }),
      failure('artifact-d', 'not_pending_deletion', { name: 'D' }),
    ])

    const text = normalizedText(wrapper)
    expect(text).toContain('Some artifacts were not deleted')
    expect(text).toContain(
      'Used by deployments: api (active), old (failed). Delete the deployments first.',
    )
    expect(text).toContain('Linked to tracks: release. Unlink the artifact from the tracks first.')
    expect(text).toContain(
      'The file could not be deleted from the bucket. Try again, or force delete to remove the artifact and leave the file in the bucket.',
    )
    expect(text).toContain('Could not be deleted. Try again.')

    const links = wrapper.findAllComponents(RouterLinkStub)
    expect(links[0].props('to')).toEqual({
      name: 'orbit-deployments',
      params: { organizationId: 'org-1', id: 'orbit-1' },
      query: { deployment: 'deployment-1' },
    })
    expect(links[1].props('to')).toEqual({
      name: 'orbit-deployments',
      params: { organizationId: 'org-1', id: 'orbit-1' },
      query: { deployment: 'deployment-2' },
    })
    expect(links[2].props('to')).toEqual({
      name: 'track',
      params: { organizationId: 'org-1', id: 'orbit-1', trackId: 'track-1' },
    })
    expect(links.every((link) => link.attributes('target') === '_blank')).toBe(true)

    deletionState.deletionResult = {
      deleted: [],
      failed: [failure('artifact-d', 'not_pending_deletion')],
    }
    await nextTick()
    expect(normalizedText(wrapper)).toContain('Artifact was not deleted')
  })

  it('offers force only for storage failures and applies it only to those entries', async () => {
    const deploymentFailure = failure('artifact-b', 'deployments', {
      deployments: [{ id: 'deployment-1', name: 'api', status: DeploymentStatusEnum.active }],
    })
    const trackFailure = failure('artifact-c', 'tracks', {
      tracks: [{ id: 'track-1', name: 'release' }],
    })
    const replacementTrackFailure = failure('artifact-a', 'tracks', {
      tracks: [{ id: 'track-2', name: 'new-link' }],
    })
    const wrapper = mountDialog([
      failure('artifact-a', 'storage_error', { name: 'A' }),
      deploymentFailure,
      trackFailure,
    ])
    artifactsStore.forceDeleteArtifacts.mockResolvedValueOnce({
      deleted: [],
      failed: [replacementTrackFailure],
    })

    await buttonByName(wrapper, 'Force delete')?.trigger('click')
    await wrapper.get('[data-testid="force-confirm"] button').trigger('click')
    await flushPromises()

    expect(artifactsStore.forceDeleteArtifacts).toHaveBeenCalledWith(['artifact-a'])
    expect(deletionState.deletionResult?.failed).toEqual([
      deploymentFailure,
      trackFailure,
      replacementTrackFailure,
    ])
    expect(normalizedText(wrapper)).toContain('api (active)')
    expect(normalizedText(wrapper)).toContain('release')
    expect(buttonByName(wrapper, 'Force delete')).toBeUndefined()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
  })

  it('removes forced storage failures while retaining unrelated blockers', async () => {
    const deploymentFailure = failure('artifact-b', 'deployments', {
      deployments: [{ id: 'deployment-1', name: 'api', status: DeploymentStatusEnum.active }],
    })
    const wrapper = mountDialog([
      failure('artifact-a', 'storage_error', { name: 'A' }),
      deploymentFailure,
    ])
    artifactsStore.forceDeleteArtifacts.mockResolvedValueOnce({
      deleted: ['artifact-a'],
      failed: [],
    })

    await buttonByName(wrapper, 'Force delete')?.trigger('click')
    await wrapper.get('[data-testid="force-confirm"] button').trigger('click')
    await flushPromises()

    expect(deletionState.deletionResult?.failed).toEqual([deploymentFailure])
    expect(normalizedText(wrapper)).toContain('api (active)')
    expect(wrapper.find('[role="dialog"]').exists()).toBe(true)
    expect(wrapper.emitted('artifactsDeleted')).toEqual([[['artifact-a']]])
    expect(toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ detail: 'Artifact "A" deleted', severity: 'success' }),
    )
  })

  it('closes only after force leaves no failure entries', async () => {
    const wrapper = mountDialog([failure('artifact-a', 'storage_error', { name: 'A' })])
    artifactsStore.forceDeleteArtifacts.mockResolvedValueOnce({
      deleted: ['artifact-a'],
      failed: [],
    })

    await buttonByName(wrapper, 'Force delete')?.trigger('click')
    await wrapper.get('[data-testid="force-confirm"] button').trigger('click')
    await flushPromises()

    expect(artifactsStore.resetDeletionResult).toHaveBeenCalledOnce()
    expect(wrapper.find('[role="dialog"]').exists()).toBe(false)
    expect(wrapper.emitted('artifactsDeleted')).toEqual([[['artifact-a']]])
  })
})
