import { shallowMount, flushPromises } from '@vue/test-utils'
import { Form } from '@primevue/forms'
import { expect, it, vi } from 'vitest'
import OrganizationCreator from './OrganizationCreator.vue'
import OrganizationInfo from './OrganizationInfo.vue'

const store = vi.hoisted(() => ({
  currentOrganization: { id: 'org', name: 'Original', logo: 'https://example.com/logo.png' },
  createOrganization: vi.fn(),
  updateOrganization: vi.fn(),
}))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => store }))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

it.each([OrganizationCreator, OrganizationInfo])(
  'does not overwrite organization logos when saving names',
  async (component) => {
    const wrapper = shallowMount(component, { global: { renderStubDefaultSlot: true } })
    wrapper.getComponent(Form).vm.$emit('submit', { valid: true, values: { name: 'Renamed' } })
    await flushPromises()
    if (component === OrganizationCreator)
      expect(store.createOrganization).toHaveBeenCalledExactlyOnceWith({ name: 'Renamed' })
    else
      expect(store.updateOrganization).toHaveBeenCalledExactlyOnceWith('org', {
        name: 'Renamed',
        logo: 'https://example.com/logo.png',
      })
    wrapper.unmount()
  },
)
