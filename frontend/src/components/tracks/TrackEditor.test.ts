import { Form, type FormInstance } from '@primevue/forms'
import { enableAutoUnmount, flushPromises, mount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import PrimeVue from 'primevue/config'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { defineComponent } from 'vue'
import { ArtifactTypeEnum } from '@/lib/api/artifacts/interfaces'
import { useTracksStore } from '@/stores/tracks'
import TrackEditor from './TrackEditor.vue'
import TracksList from './TracksList.vue'

enableAutoUnmount(afterEach)
afterEach(() => vi.unstubAllGlobals())

const mocks = vi.hoisted(() => ({ updateTrack: vi.fn(), toastAdd: vi.fn() }))

vi.mock('@/lib/api', () => ({ api: { orbitTracks: mocks } }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...((await importOriginal()) as Record<string, unknown>),
  useToast: () => ({ add: mocks.toastAdd }),
  useConfirm: () => ({ require: vi.fn() }),
}))

const stages = [
  {
    id: 'stage-1',
    track_id: 'track-1',
    name: 'Review',
    is_used: true,
    created_at: '',
    updated_at: null,
  },
  {
    id: 'stage-2',
    track_id: 'track-1',
    name: 'Staging',
    is_used: false,
    created_at: '',
    updated_at: null,
  },
]
const track = {
  id: 'track-1',
  orbit_id: 'orbit-1',
  name: 'Release track',
  artifact_type: ArtifactTypeEnum.model,
  description: '',
  tags: ['some-tag'],
  stages,
  created_by: 'User',
  next_version: 1,
  total_entries: 1,
  created_at: '',
  updated_at: null,
}

function mountPanel() {
  const pinia = createPinia()
  setActivePinia(pinia)
  const store = useTracksStore()
  store.setTracksList([structuredClone(track)])
  const wrapper = mount(
    defineComponent({
      components: { TracksList, TrackEditor },
      setup: () => ({ store }),
      template: '<TracksList :list="store.tracksList" /><TrackEditor />',
    }),
    {
      attachTo: document.body,
      global: {
        plugins: [pinia, [PrimeVue, { unstyled: true }]],
        directives: { tooltip: {} },
        stubs: {
          Dialog: {
            props: ['visible'],
            template: '<div v-if="visible"><slot /><slot name="footer" /></div>',
          },
          VirtualScroller: {
            props: ['items'],
            template:
              '<div><slot v-for="item in items" name="item" :item="item" /><slot name="content" :items="items" /></div>',
          },
          UiRichCard: {
            emits: ['edit-click'],
            template: '<button class="edit-track" @click="$emit(\'edit-click\')">Edit</button>',
          },
          Teleport: true,
        },
      },
    },
  )
  return { wrapper, store }
}

async function openPanel(wrapper: ReturnType<typeof mountPanel>['wrapper']) {
  await wrapper.get('.edit-track').trigger('click')
  await flushPromises()
}

describe('TrackEditor stages', () => {
  beforeEach(() => {
    vi.stubGlobal('matchMedia', () => ({
      matches: false,
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
    }))
    mocks.updateTrack.mockReset().mockResolvedValue(track)
  })

  it('displays the configured stages instead of defaults or track tags', async () => {
    const { wrapper } = mountPanel()
    await openPanel(wrapper)

    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual([
      'Review',
      'Staging',
    ])
    expect(wrapper.get('input[role="combobox"]').attributes('disabled')).toBeUndefined()
  })

  it('saves added and removed stages with existing IDs and displays the saved stages on reopen', async () => {
    const { wrapper, store } = mountPanel()
    await openPanel(wrapper)
    await wrapper.findAll('.remove-icon')[1].trigger('click')
    const input = wrapper.get('input[role="combobox"]')
    await input.trigger('focus')
    await input.setValue('Canary')
    await vi.waitFor(() => {
      expect(wrapper.find('[role="option"][aria-label="Canary"]').exists()).toBe(true)
    })
    await wrapper.get('[role="option"][aria-label="Canary"]').trigger('click')
    await flushPromises()
    const savedStages = [stages[0], { ...stages[1], id: 'stage-3', name: 'Canary' }]
    mocks.updateTrack.mockResolvedValue({ ...track, stages: savedStages })

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.updateTrack).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', 'track-1', {
      name: 'Release track',
      description: '',
      stages: [{ id: 'stage-1', name: 'Review' }, { name: 'Canary' }],
    })
    expect(store.editorVisible).toBe(false)
    expect(store.tracksList[0].stages).toEqual(savedStages)
    await openPanel(wrapper)
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual([
      'Review',
      'Canary',
    ])
  })

  it('prevents removing stages linked to artifacts without locking unused stages', async () => {
    const { wrapper, store } = mountPanel()
    await openPanel(wrapper)
    await wrapper.findAll('.remove-icon')[0].trigger('click')
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual([
      'Review',
      'Staging',
    ])
    await wrapper.findAll('.remove-icon')[1].trigger('click')
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual(['Review'])
    expect(store.tracksList[0].stages).toEqual(stages)
  })

  it('allows Backspace to remove unused stages and retains linked stages when saving', async () => {
    const { wrapper } = mountPanel()
    await openPanel(wrapper)
    const input = wrapper.get('input[role="combobox"]')
    await input.trigger('keydown', { key: 'Backspace', code: 'Backspace' })
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual(['Review'])
    await input.trigger('keydown', { key: 'Backspace', code: 'Backspace' })
    await input.trigger('keydown', { key: 'Backspace', code: 'Backspace' })
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual(['Review'])

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(mocks.updateTrack).toHaveBeenCalledExactlyOnceWith('org-1', 'orbit-1', 'track-1', {
      name: 'Release track',
      description: '',
      stages: [{ id: 'stage-1', name: 'Review' }],
    })
  })

  it('protects linked stages selected with arrow keys while allowing unused stages to be removed', async () => {
    const { wrapper } = mountPanel()
    await openPanel(wrapper)
    const input = wrapper.get('input[role="combobox"]')
    await input.trigger('focus')
    await input.trigger('keydown', { key: 'ArrowLeft', code: 'ArrowLeft' })
    const listbox = wrapper.get('ul[role="listbox"][aria-orientation="horizontal"]')
    await listbox.trigger('keydown', { key: 'ArrowLeft', code: 'ArrowLeft' })
    await listbox.trigger('keydown', { key: 'Backspace', code: 'Backspace' })
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual([
      'Review',
      'Staging',
    ])

    await listbox.trigger('keydown', { key: 'ArrowRight', code: 'ArrowRight' })
    await listbox.trigger('keydown', { key: 'Backspace', code: 'Backspace' })
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual(['Review'])
  })

  it('allows Backspace to edit stage input text when the last selected stage is linked', async () => {
    const { wrapper } = mountPanel()
    await openPanel(wrapper)
    await wrapper.findAll('.remove-icon')[1].trigger('click')
    const input = wrapper.get('input[role="combobox"]')
    await input.setValue('Canary')
    const event = new KeyboardEvent('keydown', {
      key: 'Backspace',
      code: 'Backspace',
      bubbles: true,
      cancelable: true,
    })
    input.element.dispatchEvent(event)

    expect(event.defaultPrevented).toBe(false)
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual(['Review'])
  })

  it.each([{ names: [] }, { names: [''] }, { names: ['s'.repeat(101)] }])(
    'rejects invalid stages $names',
    async ({ names }) => {
      const { wrapper } = mountPanel()
      await openPanel(wrapper)
      const form = wrapper.getComponent(Form).vm as unknown as FormInstance
      form.setFieldValue('stages', names)
      await wrapper.get('form').trigger('submit')
      await flushPromises()

      expect(mocks.updateTrack).not.toHaveBeenCalled()
    },
  )

  it('keeps unsaved stages available for retry when saving fails', async () => {
    const { wrapper, store } = mountPanel()
    await openPanel(wrapper)
    await wrapper.findAll('.remove-icon')[1].trigger('click')
    mocks.updateTrack.mockRejectedValue(new Error('Could not save stages'))
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(store.editorVisible).toBe(true)
    expect(store.tracksList[0].stages).toEqual(stages)
    expect(wrapper.findAll('[data-pc-name="chip"]').map((chip) => chip.text())).toEqual(['Review'])
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(mocks.toastAdd).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Could not save stages' }),
    )
  })
})
