import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { SatelliteStatusEnum, type Satellite } from '@/lib/api/satellites/interfaces'
import SatellitesEditModal from './SatellitesEditModal.vue'

const { updateSatellite, addToast } = vi.hoisted(() => ({
  updateSatellite: vi.fn(),
  addToast: vi.fn(),
}))

vi.mock('@/stores/satellites', () => ({
  useSatellitesStore: () => ({ updateSatellite }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'organization-1', id: 'orbit-1' } }),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: addToast }),
}))

const satellite: Satellite = {
  id: 'satellite-1',
  orbit_id: 'orbit-1',
  name: 'Satellite',
  description: 'Original description',
  base_url: null,
  paired: true,
  capabilities: {},
  present_capabilities: [],
  created_at: '2026-01-01T00:00:00Z',
  updated_at: '2026-01-01T00:00:00Z',
  last_seen_at: '2026-01-01T00:00:00Z',
  status: SatelliteStatusEnum.active,
}

function mountModal() {
  return mount(SatellitesEditModal, {
    props: { data: satellite, visible: false },
    global: {
      plugins: [PrimeVue],
      stubs: {
        UiDialogRight: {
          props: ['visible', 'footerActions'],
          template:
            '<div v-if="visible"><slot /><button v-bind="footerActions.rightButton.props">Save changes</button></div>',
        },
        SatelliteDelete: true,
      },
    },
  })
}

describe('SatellitesEditModal', () => {
  let wrapper: ReturnType<typeof mountModal>

  beforeEach(async () => {
    updateSatellite.mockReset().mockResolvedValue(undefined)
    addToast.mockReset()
    wrapper = mountModal()
    await wrapper.setProps({ visible: true })
    await flushPromises()
  })

  afterEach(() => {
    wrapper.unmount()
  })

  it.each([
    [
      { response: { data: { detail: 'Satellite name already exists' } } },
      'Satellite name already exists',
    ],
    [{}, 'Failed to update satellite'],
  ])('shows only an error toast when the update fails (%j)', async (error, message) => {
    updateSatellite.mockRejectedValueOnce(error)
    await wrapper.get('input[name="name"]').setValue('Existing satellite')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(updateSatellite).toHaveBeenCalledWith('organization-1', 'orbit-1', satellite.id, {
      name: 'Existing satellite',
      description: satellite.description,
    })
    expect(addToast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: message }),
    )
    expect(wrapper.emitted('update:visible')).toBeUndefined()
    expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
  })

  it('shows success and closes the modal only after the update succeeds', async () => {
    let resolveUpdate!: () => void
    updateSatellite.mockReturnValueOnce(
      new Promise<void>((resolve) => {
        resolveUpdate = resolve
      }),
    )
    await wrapper.get('input[name="name"]').setValue('Renamed satellite')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('button').attributes('disabled')).toBeDefined()
    expect(addToast).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')).toBeUndefined()

    resolveUpdate()
    await flushPromises()

    expect(addToast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'success', detail: 'Satellite updated successfully.' }),
    )
    expect(wrapper.emitted('update:visible')).toEqual([[false]])
    expect(wrapper.find('form').exists()).toBe(false)
  })

  it('does not update or show a toast for an invalid name', async () => {
    await wrapper.get('input[name="name"]').setValue('')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(updateSatellite).not.toHaveBeenCalled()
    expect(addToast).not.toHaveBeenCalled()
    expect(wrapper.emitted('update:visible')).toBeUndefined()
    expect(wrapper.get('button').attributes('disabled')).toBeUndefined()
  })
})
