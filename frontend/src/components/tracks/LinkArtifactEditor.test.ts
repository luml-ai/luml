import { Form, type FormInstance } from '@primevue/forms'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import type { TrackEntry } from '@/lib/api/orbit-tracks/interfaces'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import LinkArtifactEditor from './LinkArtifactEditor.vue'
import StageWarning from './StageWarning.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.unstubAllGlobals())

const mocks = vi.hoisted(() => ({
  patchEntry: vi.fn(),
  deleteEntry: vi.fn(),
  getEntryByStage: vi.fn(),
  toastAdd: vi.fn(),
  confirmRequire: vi.fn(),
}))

vi.mock('@/lib/api', () => ({ api: { orbitTracks: mocks } }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
}))
vi.mock('@/stores/tracks', () => ({
  useTracksStore: () => ({
    trackStages: [
      { id: 'production', name: 'Production' },
      { id: 'staging', name: 'Staging' },
    ],
  }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: mocks.toastAdd }),
}))
vi.mock('primevue/useconfirm', () => ({
  useConfirm: () => ({ require: mocks.confirmRequire }),
}))

const entry: TrackEntry = {
  id: 'entry-1',
  track_id: 'track-1',
  artifact_id: 'artifact-1',
  artifact_collection_id: 'collection-1',
  version: 3,
  stage_id: 'production',
  stage_name: 'Production',
  added_by: 'User',
  created_at: '',
  updated_at: null,
  artifact_name: 'Model',
  artifact_description: null,
}
const clearedEntry = { ...entry, stage_id: null, stage_name: null }

async function mountEditor(initialEntry = entry) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useArtifactLinksStore()
  store.setEntriesList([initialEntry])
  store.showEditor(initialEntry)
  const wrapper = mount(LinkArtifactEditor, {
    global: {
      plugins: [pinia, [PrimeVue, { unstyled: true }]],
      stubs: {
        Dialog: {
          props: ['visible'],
          template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
        },
        Teleport: true,
      },
    },
  })
  await flushPromises()
  return { wrapper, store }
}

describe('LinkArtifactEditor stage removal', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
    vi.clearAllMocks()
    mocks.patchEntry.mockReset().mockResolvedValue(clearedEntry)
    mocks.getEntryByStage.mockReset().mockResolvedValue(entry)
  })

  it('clears the stage without unlinking the entry or changing its version', async () => {
    const { wrapper, store } = await mountEditor()

    await wrapper.get('[data-pc-section="clearicon"]').trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.patchEntry).toHaveBeenCalledExactlyOnceWith(
      'org-1',
      'orbit-1',
      'track-1',
      'entry-1',
      { stage_id: null },
      false,
    )
    expect(store.entriesList).toEqual([clearedEntry])
    expect(store.entriesList[0].version).toBe(3)
    expect(mocks.deleteEntry).not.toHaveBeenCalled()
    expect(mocks.confirmRequire).not.toHaveBeenCalled()
    expect(store.editableEntry).toBeNull()
  })

  it('saves an entry that already has no stage', async () => {
    const { wrapper } = await mountEditor(clearedEntry)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.patchEntry).toHaveBeenCalledWith(
      'org-1',
      'orbit-1',
      'track-1',
      'entry-1',
      { stage_id: null },
      false,
    )
  })

  it('lets another entry use the cleared stage while retaining both entries and versions', async () => {
    const { wrapper, store } = await mountEditor()
    const otherEntry = { ...clearedEntry, id: 'entry-2', artifact_id: 'artifact-2', version: 4 }
    store.setEntriesList([entry, otherEntry])
    await wrapper.get('[data-pc-section="clearicon"]').trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    mocks.getEntryByStage.mockRejectedValue(new Error('Stage is empty'))
    store.showEditor(otherEntry)
    await flushPromises()
    const form = wrapper.getComponent(Form).vm as unknown as FormInstance
    form.setFieldValue('stage_id', 'production')
    await flushPromises()
    const reassignedEntry = { ...otherEntry, stage_id: 'production', stage_name: 'Production' }
    mocks.patchEntry.mockResolvedValue(reassignedEntry)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.patchEntry).toHaveBeenLastCalledWith(
      'org-1',
      'orbit-1',
      'track-1',
      'entry-2',
      { stage_id: 'production' },
      false,
    )
    expect(store.entriesList).toEqual([clearedEntry, reassignedEntry])
    expect(mocks.confirmRequire).not.toHaveBeenCalled()
    expect(mocks.deleteEntry).not.toHaveBeenCalled()
  })

  it('keeps the saved stage when clearing is cancelled', async () => {
    const { wrapper, store } = await mountEditor()
    await wrapper.get('[data-pc-section="clearicon"]').trigger('click')
    wrapper.getComponent({ name: 'UiDialogRight' }).vm.$emit('update:visible', false)
    await flushPromises()

    expect(store.entriesList).toEqual([entry])
    expect(mocks.patchEntry).not.toHaveBeenCalled()
  })

  it('keeps the editor open and the saved entry unchanged when clearing fails', async () => {
    mocks.patchEntry.mockRejectedValue(new Error('Could not clear stage'))
    const { wrapper, store } = await mountEditor()
    await wrapper.get('[data-pc-section="clearicon"]').trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(store.entriesList).toEqual([entry])
    expect(store.editableEntry).toEqual(entry)
    expect(mocks.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Could not clear stage' }),
    )
    mocks.patchEntry.mockResolvedValue(clearedEntry)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(store.entriesList).toEqual([clearedEntry])
  })

  it('clears an occupied selection without requesting reassignment', async () => {
    mocks.getEntryByStage.mockResolvedValue({ ...entry, id: 'entry-2' })
    const { wrapper } = await mountEditor()
    expect(wrapper.findComponent(StageWarning).exists()).toBe(true)

    await wrapper.get('[data-pc-section="clearicon"]').trigger('click')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.findComponent(StageWarning).exists()).toBe(false)
    expect(mocks.confirmRequire).not.toHaveBeenCalled()
    expect(mocks.patchEntry).toHaveBeenCalled()
  })

  it('ignores a pending occupied-stage lookup after the stage is cleared', async () => {
    let resolveLookup!: (value: TrackEntry) => void
    mocks.getEntryByStage.mockReturnValue(
      new Promise<TrackEntry>((resolve) => {
        resolveLookup = resolve
      }),
    )
    const { wrapper } = await mountEditor()
    await wrapper.get('[data-pc-section="clearicon"]').trigger('click')
    resolveLookup({ ...entry, id: 'entry-2' })
    await flushPromises()

    expect(wrapper.findComponent(StageWarning).exists()).toBe(false)
    await wrapper.get('form').trigger('submit')
    await flushPromises()
    expect(mocks.confirmRequire).not.toHaveBeenCalled()
    expect(mocks.patchEntry).toHaveBeenCalled()
  })

  it('still allows switching to an available stage', async () => {
    const { wrapper, store } = await mountEditor()
    mocks.getEntryByStage.mockRejectedValue(new Error('Stage is empty'))
    const form = wrapper.getComponent(Form).vm as unknown as FormInstance
    form.setFieldValue('stage_id', 'staging')
    await flushPromises()
    const updatedEntry = { ...entry, stage_id: 'staging', stage_name: 'Staging' }
    mocks.patchEntry.mockResolvedValue(updatedEntry)
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.patchEntry).toHaveBeenCalledWith(
      'org-1',
      'orbit-1',
      'track-1',
      'entry-1',
      { stage_id: 'staging' },
      false,
    )
    expect(store.entriesList).toEqual([updatedEntry])
  })
})
