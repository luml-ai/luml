import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import type { Organization } from '@/lib/api/api.interfaces'
import { useOrganizationStore } from '@/stores/organization'
import OrganizationDelete from './OrganizationDelete.vue'

const harness = vi.hoisted(() => ({ routerPush: vi.fn(), toastAdd: vi.fn() }))

vi.mock('vue-router', () => ({ useRouter: () => ({ push: harness.routerPush }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: harness.toastAdd }),
}))
vi.mock('@/lib/api', () => ({ api: {} }))

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.resetAllMocks()
})

it('retains the replacement selected by the store after deletion', async () => {
  const store = useOrganizationStore()
  const first = { id: 'organization-a', name: 'A' } as Organization
  const second = { id: 'organization-b', name: 'B' } as Organization
  store.availableOrganizations = [first, second]
  store.setCurrentOrganizationId(first.id)
  vi.spyOn(store, 'deleteOrganization').mockImplementation(async () => {
    store.availableOrganizations = [second]
    store.setCurrentOrganizationId(second.id)
  })
  const wrapper = shallowMount(OrganizationDelete, {
    global: {
      stubs: {
        Button: { template: '<button><slot /></button>' },
        Dialog: { template: '<div><slot /><slot name="footer" /></div>' },
      },
    },
  })

  await wrapper.findComponent({ name: 'Checkbox' }).vm.$emit('update:modelValue', true)
  await wrapper.findAll('button')[2].trigger('click')
  await flushPromises()

  expect(store.deleteOrganization).toHaveBeenCalledWith(first.id)
  expect(store.currentOrganization).toEqual(second)
  expect(harness.routerPush).toHaveBeenCalledWith({ name: 'home' })
  expect(harness.toastAdd).toHaveBeenCalledOnce()
  wrapper.unmount()
})
