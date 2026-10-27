import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import ConfirmationService from 'primevue/confirmationservice'
import ConfirmDialog from 'primevue/confirmdialog'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { PermissionEnum } from '@/lib/api/api.interfaces'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import type { TrackEntry, TrackStage } from '@/lib/api/orbit-tracks/interfaces'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import { useTracksStore } from '@/stores/tracks'
import LinksToolbar from './LinksToolbar.vue'
import LinkArtifactEditor from './LinkArtifactEditor.vue'
import TrackEditor from './TrackEditor.vue'

enableAutoUnmount(afterEach)

const mocks = vi.hoisted(() => ({
  deleteEntry: vi.fn(),
  deleteEntries: vi.fn(),
  deleteTrack: vi.fn(),
  toastAdd: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: {
    orbitTracks: {
      deleteEntry: mocks.deleteEntry,
      deleteEntries: mocks.deleteEntries,
      deleteTrack: mocks.deleteTrack,
      getEntryByStage: vi.fn().mockRejectedValue(new Error('No stage selected')),
    },
  },
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
}))
vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({
    getCurrentOrbitPermissions: { track: [PermissionEnum.delete], artifact: [] },
  }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: mocks.toastAdd }),
}))

const entry: TrackEntry = {
  id: 'entry-1',
  track_id: 'track-1',
  artifact_id: 'artifact-1',
  artifact_collection_id: 'collection-1',
  version: 1,
  stage_id: 'stage-1',
  stage_name: 'Production',
  artifact_name: 'Model',
  artifact_description: '',
  added_by: 'User',
  created_at: '',
  updated_at: null,
}
const production: TrackStage = {
  id: 'stage-1',
  track_id: 'track-1',
  name: 'Production',
  is_used: true,
  created_at: '',
  updated_at: null,
}
const unused: TrackStage = { ...production, id: 'stage-2', name: 'Staging', is_used: false }

function mountDeletion(
  component: typeof LinksToolbar | typeof LinkArtifactEditor | typeof TrackEditor,
) {
  const pinia = createPinia()
  setActivePinia(pinia)
  const links = useArtifactLinksStore()
  const tracks = useTracksStore()
  links.setEntriesList([entry])
  links.selectedEntries = [entry]
  links.showEditor(entry)
  tracks.showEditor({
    id: 'track-1',
    name: 'Release',
    description: '',
    stages: [production, unused],
  })
  tracks.setTracksList([
    {
      id: 'track-1',
      name: 'Release',
      orbit_id: 'orbit-1',
      artifact_type: ArtifactTypeEnum.model,
      description: '',
      tags: [],
      stages: [production, unused],
      total_entries: 1,
      next_version: 2,
      created_by: 'User',
      created_at: '',
      updated_at: null,
    },
  ])
  const wrapper = mount(
    defineComponent({
      components: { Deletion: component, ConfirmDialog },
      template: '<Deletion /><ConfirmDialog />',
    }),
    {
      attachTo: document.body,
      global: {
        plugins: [pinia, [PrimeVue, { unstyled: true }], ConfirmationService],
        directives: { tooltip: {} },
        stubs: {
          UiDialogRight: {
            props: ['footerActions'],
            template:
              '<div><button @click="footerActions.leftButton.props.onClick()">{{ footerActions.leftButton.props.label }}</button></div>',
          },
        },
      },
    },
  )
  return { wrapper, links, tracks }
}

async function clickDialogButton(label: string) {
  const button = Array.from(
    document.body.querySelectorAll<HTMLButtonElement>('[role="alertdialog"] button'),
  ).find((button) => button.textContent?.trim() === label)
  expect(button).toBeDefined()
  if (!button) throw new Error(`Dialog button ${label} was not found`)
  button.click()
  await flushPromises()
}

function dialogText() {
  return document.body.querySelector('[role="alertdialog"]')?.textContent ?? ''
}

describe('track deletion stage warnings', () => {
  beforeEach(() => {
    mocks.deleteEntry.mockReset().mockResolvedValue(undefined)
    mocks.deleteEntries.mockReset().mockResolvedValue(undefined)
    mocks.deleteTrack.mockReset().mockResolvedValue(undefined)
  })

  it.each([
    ['toolbar', LinksToolbar],
    ['entry settings', LinkArtifactEditor],
  ] as const)(
    'warns before unlinking a staged entry from %s and allows cancellation',
    async (_, component) => {
      const { wrapper, links } = mountDeletion(component)
      await wrapper.get('button').trigger('click')
      await flushPromises()

      expect(dialogText()).toContain('current Production')
      expect(dialogText()).toContain('free the Production stage')
      expect(dialogText()).toContain('will not delete the artifact')
      expect(mocks.deleteEntry).not.toHaveBeenCalled()
      await clickDialogButton('Cancel')
      expect(mocks.deleteEntry).not.toHaveBeenCalled()
      expect(links.entriesList).toHaveLength(1)

      await wrapper.get('button').trigger('click')
      await flushPromises()
      await clickDialogButton('Unlink artifact')
      expect(mocks.deleteEntry).toHaveBeenCalledExactlyOnceWith(
        'org-1',
        'orbit-1',
        'track-1',
        'entry-1',
      )
      expect(links.entriesList).toHaveLength(0)
    },
  )

  it('lists all affected stages when unlinking multiple entries', async () => {
    const { wrapper, links } = mountDeletion(LinksToolbar)
    links.selectedEntries = [
      entry,
      { ...entry, id: 'entry-2', stage_id: 'stage-2', stage_name: 'Canary' },
      { ...entry, id: 'entry-3', stage_id: null, stage_name: null },
    ]
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(dialogText()).toContain('free')
    expect(dialogText()).toContain('Production')
    expect(dialogText()).toContain('Canary')
    expect(dialogText()).toContain('These artifacts will be unlinked')
    expect(dialogText()).toContain('access the artifacts in their collections')
    expect(mocks.deleteEntries).not.toHaveBeenCalled()
    await clickDialogButton('Unlink artifacts')
    expect(mocks.deleteEntries).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', 'track-1', [
      'entry-1',
      'entry-2',
      'entry-3',
    ])
  })

  it.each([
    ['toolbar', LinksToolbar],
    ['entry settings', LinkArtifactEditor],
  ] as const)('keeps regular confirmation for unstaged entries from %s', async (_, component) => {
    const { wrapper, links } = mountDeletion(component)
    const unstaged = { ...entry, stage_id: null, stage_name: null }
    links.selectedEntries = [unstaged]
    links.showEditor(unstaged)
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(dialogText()).toContain('will not delete the artifact')
    expect(dialogText()).not.toContain('free')
    await clickDialogButton('Unlink artifact')
    expect(mocks.deleteEntry).toHaveBeenCalledOnce()
  })

  it('warns about occupied stages before deleting a whole track and allows cancellation', async () => {
    const { wrapper, tracks } = mountDeletion(TrackEditor)
    if (!tracks.editableTrack) throw new Error('Track editor is not open')
    tracks.editableTrack.stages.push({ ...production, id: 'stage-3', name: 'Canary' })
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(dialogText()).toContain('free')
    expect(dialogText()).toContain('Production')
    expect(dialogText()).toContain('Canary')
    expect(dialogText()).not.toContain('Staging')
    expect(dialogText()).toContain('collections')
    expect(mocks.deleteTrack).not.toHaveBeenCalled()
    await clickDialogButton('Cancel')
    expect(mocks.deleteTrack).not.toHaveBeenCalled()
    expect(tracks.tracksList).toHaveLength(1)

    await wrapper.get('button').trigger('click')
    await flushPromises()
    await clickDialogButton('Delete')
    expect(mocks.deleteTrack).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', 'track-1')
    expect(tracks.tracksList).toHaveLength(0)
  })

  it('keeps regular confirmation for a track without occupied stages', async () => {
    const { wrapper, tracks } = mountDeletion(TrackEditor)
    if (!tracks.editableTrack) throw new Error('Track editor is not open')
    tracks.editableTrack.stages = [unused]
    await wrapper.get('button').trigger('click')
    await flushPromises()

    expect(dialogText()).toContain('cannot be undone')
    expect(dialogText()).not.toContain('free')
    await clickDialogButton('Delete')
    expect(mocks.deleteTrack).toHaveBeenCalledOnce()
  })

  it('keeps an entry available when confirmed deletion fails', async () => {
    const { wrapper, links } = mountDeletion(LinksToolbar)
    mocks.deleteEntry.mockRejectedValue(new Error('Deletion failed'))
    await wrapper.get('button').trigger('click')
    await flushPromises()
    await clickDialogButton('Unlink artifact')

    expect(links.entriesList).toHaveLength(1)
    expect(links.selectedEntries).toHaveLength(1)
    expect(mocks.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Deletion failed' }),
    )
  })
})
