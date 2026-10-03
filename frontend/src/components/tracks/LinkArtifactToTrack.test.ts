import { Form, type FormInstance } from '@primevue/forms'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { InputText } from 'primevue'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { TrackEntry } from '@/lib/api/orbit-tracks/interfaces'
import LinkArtifactToTrack from './LinkArtifactToTrack.vue'
import StageWarning from './StageWarning.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.unstubAllGlobals())

const mocks = vi.hoisted(() => ({
  addEntry: vi.fn(),
  getEntryByStage: vi.fn(),
  listStages: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
}))

vi.mock('@/stores/tracks', () => ({
  useTracksStore: () => ({
    trackStages: [
      { id: 'production', name: 'Production' },
      { id: 'staging', name: 'Staging' },
    ],
    listStages: mocks.listStages,
    resetTrackStages: vi.fn(),
    reset: vi.fn(),
  }),
}))

vi.mock('@/stores/artifact-links/artifact-links', () => ({
  useArtifactLinksStore: () => mocks,
}))

vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: mocks.toastAdd }),
}))

const occupiedEntry: TrackEntry = {
  id: 'entry-1',
  track_id: 'track-1',
  artifact_id: 'other-artifact',
  artifact_collection_id: 'collection-1',
  version: 1,
  stage_id: 'production',
  added_by: 'User',
  created_at: '',
  updated_at: null,
  artifact_name: 'Previous model',
  artifact_description: null,
  stage_name: 'Production',
}

function mountLinkDialog() {
  return mount(LinkArtifactToTrack, {
    props: { artifactId: 'artifact-1', artifactType: ArtifactTypeEnum.model, existingTracks: [] },
    global: {
      plugins: [[PrimeVue, { unstyled: true }]],
      directives: { tooltip: {} },
      stubs: {
        Dialog: { template: '<div><slot /><slot name="footer" /></div>' },
        TracksSelect: {
          components: { InputText },
          template: '<InputText name="track_id" />',
        },
      },
    },
  })
}

async function selectTrackAndStage(wrapper: ReturnType<typeof mountLinkDialog>, stageId?: string) {
  await wrapper.get('input[name="track_id"]').setValue('track-1')
  await flushPromises()
  if (stageId) {
    const form = wrapper.getComponent(Form).vm as unknown as FormInstance
    form.setFieldValue('stage_id', stageId)
    await flushPromises()
  }
}

describe('LinkArtifactToTrack occupied stages', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
    mocks.addEntry.mockReset().mockResolvedValue(undefined)
    mocks.getEntryByStage.mockReset().mockRejectedValue(new Error('Stage is empty'))
  })

  it('explains an occupied stage is unavailable and disables linking', async () => {
    mocks.getEntryByStage.mockResolvedValue(occupiedEntry)
    const wrapper = mountLinkDialog()
    await selectTrackAndStage(wrapper, 'production')

    expect(mocks.getEntryByStage).toHaveBeenCalledWith('track-1', 'production')
    expect(wrapper.text()).toContain('This stage is already in use by another artifact.')
    expect(wrapper.text()).toContain(
      'The artifact Previous model is assigned to this stage. Choose another stage or leave the stage unassigned to link this artifact.',
    )
    expect(wrapper.text()).not.toContain('Once confirmed')
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(mocks.addEntry).not.toHaveBeenCalled()
  })

  it('removes the warning and allows linking after choosing an available stage', async () => {
    mocks.getEntryByStage.mockResolvedValueOnce(occupiedEntry)
    const wrapper = mountLinkDialog()
    await selectTrackAndStage(wrapper, 'production')
    const form = wrapper.getComponent(Form).vm as unknown as FormInstance
    form.setFieldValue('stage_id', 'staging')
    await flushPromises()

    expect(wrapper.findComponent(StageWarning).exists()).toBe(false)
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.addEntry).toHaveBeenCalledExactlyOnceWith('track-1', {
      artifact_id: 'artifact-1',
      stage_id: 'staging',
    })
    expect(wrapper.emitted('tracks-changed')).toHaveLength(1)
  })

  it('allows linking without a stage after clearing the occupied selection', async () => {
    mocks.getEntryByStage.mockResolvedValue(occupiedEntry)
    const wrapper = mountLinkDialog()
    await selectTrackAndStage(wrapper, 'production')
    const form = wrapper.getComponent(Form).vm as unknown as FormInstance
    form.setFieldValue('stage_id', undefined)
    await flushPromises()

    expect(wrapper.findComponent(StageWarning).exists()).toBe(false)
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.addEntry).toHaveBeenCalledExactlyOnceWith('track-1', {
      artifact_id: 'artifact-1',
    })
  })

  it('keeps an invalid form disabled', async () => {
    const wrapper = mountLinkDialog()
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(mocks.addEntry).not.toHaveBeenCalled()
  })

  it('preserves the selection and reports a linking failure', async () => {
    mocks.addEntry.mockRejectedValue(new Error('Link failed'))
    const wrapper = mountLinkDialog()
    await selectTrackAndStage(wrapper, 'production')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    const form = wrapper.getComponent(Form).vm as unknown as FormInstance
    expect(form.getFieldState('stage_id')?.value).toBe('production')
    expect(wrapper.emitted('tracks-changed')).toBeUndefined()
    expect(mocks.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Link failed' }),
    )
  })

  it('retains the reassignment confirmation message for the artifact editor', () => {
    const wrapper = mount(StageWarning, { props: { artifact: occupiedEntry } })

    expect(wrapper.text()).toContain(
      'Once confirmed, the artifact Previous model will be unlinked from this stage.',
    )
  })
})
