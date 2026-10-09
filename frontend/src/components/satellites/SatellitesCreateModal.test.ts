import { flushPromises, mount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { Form } from '@primevue/forms'
import SatellitesCreateModal from './SatellitesCreateModal.vue'

const { createSatellite, addToast } = vi.hoisted(() => ({
  createSatellite: vi.fn(),
  addToast: vi.fn(),
}))

vi.mock('@/stores/satellites', () => ({
  useSatellitesStore: () => ({ createSatellite }),
}))

vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'organization-1', id: 'orbit-1' } }),
}))

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: addToast }),
}))

const response = { satellite: { id: 'satellite-1' } }

function mountModal() {
  return mount(SatellitesCreateModal, {
    props: { visible: true },
    global: {
      plugins: [PrimeVue],
      stubs: { Dialog: { template: '<div><slot /></div>' } },
    },
  })
}

describe('SatellitesCreateModal', () => {
  let wrapper: ReturnType<typeof mountModal>

  beforeEach(() => {
    createSatellite.mockReset().mockResolvedValue(response)
    addToast.mockReset()
    wrapper = mountModal()
  })

  afterEach(() => {
    wrapper.unmount()
  })

  it('disables Create and ignores repeat submissions while creation is pending', async () => {
    let resolveCreate!: (value: typeof response) => void
    createSatellite.mockReturnValueOnce(
      new Promise<typeof response>((resolve) => {
        resolveCreate = resolve
      }),
    )
    await wrapper.get('input[name="name"]').setValue('New satellite')
    await wrapper.get('textarea[name="description"]').setValue('Satellite description')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()
    expect(createSatellite).toHaveBeenCalledExactlyOnceWith('organization-1', 'orbit-1', {
      name: 'New satellite',
      description: 'Satellite description',
    })
    expect(wrapper.emitted('create')).toBeUndefined()

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(createSatellite).toHaveBeenCalledTimes(1)

    resolveCreate(response)
    await flushPromises()

    expect(wrapper.emitted('create')).toEqual([[response]])
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(addToast).not.toHaveBeenCalled()
  })

  it('ignores a second submit before the button has rendered its disabled state', async () => {
    let resolveCreate!: (value: typeof response) => void
    createSatellite.mockReturnValueOnce(
      new Promise<typeof response>((resolve) => {
        resolveCreate = resolve
      }),
    )
    await wrapper.get('input[name="name"]').setValue('New satellite')

    const form = wrapper.getComponent(Form)
    form.vm.$emit('submit', { valid: true })
    form.vm.$emit('submit', { valid: true })

    expect(createSatellite).toHaveBeenCalledTimes(1)

    resolveCreate(response)
    await flushPromises()

    expect(wrapper.emitted('create')).toEqual([[response]])
  })

  it('re-enables Create after failure and allows a retry', async () => {
    let rejectCreate!: (reason: Error) => void
    createSatellite.mockReturnValueOnce(
      new Promise((_, reject) => {
        rejectCreate = reject
      }),
    )
    await wrapper.get('input[name="name"]').setValue('New satellite')
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeDefined()

    rejectCreate(new Error('Creation failed'))
    await flushPromises()

    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
    expect(wrapper.emitted('create')).toBeUndefined()
    expect(addToast).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'Creation failed' }),
    )

    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(createSatellite).toHaveBeenCalledTimes(2)
    expect(wrapper.emitted('create')).toEqual([[response]])
  })

  it('does not create a satellite or disable Create for an invalid name', async () => {
    await wrapper.get('form').trigger('submit')
    await flushPromises()

    expect(createSatellite).not.toHaveBeenCalled()
    expect(wrapper.emitted('create')).toBeUndefined()
    expect(addToast).not.toHaveBeenCalled()
    expect(wrapper.get('button[type="submit"]').attributes('disabled')).toBeUndefined()
  })
})
