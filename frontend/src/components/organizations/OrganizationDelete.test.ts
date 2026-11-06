import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, expect, it, vi } from 'vitest'
import type { Organization, OrganizationDetails } from '@/lib/api/api.interfaces'
import { useOrganizationStore } from '@/stores/organization'
import OrganizationDelete from './OrganizationDelete.vue'

const harness = vi.hoisted(() => ({ routerReplace: vi.fn(), toastAdd: vi.fn() }))

vi.mock('vue-router', () => ({ useRouter: () => ({ replace: harness.routerReplace }) }))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: harness.toastAdd }),
}))
vi.mock('@/lib/api', () => ({ api: {} }))

function mountDelete() {
  return shallowMount(OrganizationDelete, {
    global: {
      directives: { tooltip: () => undefined },
      stubs: {
        Button: { template: '<button :disabled="$attrs.disabled"><slot /></button>' },
        Dialog: { template: '<div><slot /><slot name="footer" /></div>' },
      },
    },
  })
}

async function confirmDeletion() {
  const wrapper = mountDelete()
  await wrapper.findComponent({ name: 'Checkbox' }).vm.$emit('update:modelValue', true)
  await wrapper.findAll('button')[2].trigger('click')
  await flushPromises()
  return wrapper
}

function selectFirstOf(organizations: [Organization, ...Organization[]]) {
  const store = useOrganizationStore()
  store.availableOrganizations = organizations
  store.setCurrentOrganizationId(organizations[0].id)
  return store
}

beforeEach(() => {
  setActivePinia(createPinia())
  localStorage.clear()
  vi.resetAllMocks()
})

it('retains the replacement selected by the store after deletion', async () => {
  const first = { id: 'organization-a', name: 'A' } as Organization
  const second = { id: 'organization-b', name: 'B' } as Organization
  const store = selectFirstOf([first, second])
  vi.spyOn(store, 'deleteOrganization').mockImplementation(async () => {
    store.availableOrganizations = [second]
    store.setCurrentOrganizationId(second.id)
  })
  const wrapper = await confirmDeletion()

  expect(store.deleteOrganization).toHaveBeenCalledWith(first.id)
  expect(store.currentOrganization).toEqual(second)
  expect(harness.routerReplace).toHaveBeenCalledWith({ name: 'home' })
  expect(harness.toastAdd).toHaveBeenCalledOnce()
  wrapper.unmount()
})

it('leaves the page and reports success when only the replacement fails to load', async () => {
  const first = { id: 'organization-a', name: 'A' } as Organization
  const second = { id: 'organization-b', name: 'B' } as Organization
  const store = selectFirstOf([first, second])
  vi.spyOn(store, 'deleteOrganization').mockImplementation(async () => {
    store.availableOrganizations = [second]
    throw new Error('Orbits unavailable')
  })

  const wrapper = await confirmDeletion()

  expect(harness.routerReplace).toHaveBeenCalledWith({ name: 'home' })
  expect(harness.toastAdd).toHaveBeenCalledTimes(2)
  expect(harness.toastAdd).toHaveBeenNthCalledWith(
    1,
    expect.objectContaining({ severity: 'error' }),
  )
  expect(harness.toastAdd).toHaveBeenNthCalledWith(
    2,
    expect.objectContaining({ severity: 'success' }),
  )
  wrapper.unmount()
})

it('stays on the page when the deletion itself fails', async () => {
  const first = { id: 'organization-a', name: 'A' } as Organization
  const second = { id: 'organization-b', name: 'B' } as Organization
  const store = selectFirstOf([first, second])
  vi.spyOn(store, 'deleteOrganization').mockRejectedValue(new Error('Forbidden'))

  const wrapper = await confirmDeletion()

  expect(harness.routerReplace).not.toHaveBeenCalled()
  expect(harness.toastAdd).toHaveBeenCalledOnce()
  expect(harness.toastAdd).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
  wrapper.unmount()
})

it('blocks deletion while other members remain', async () => {
  const store = selectFirstOf([
    { id: 'organization-a', name: 'A' } as Organization,
    { id: 'organization-b', name: 'B' } as Organization,
  ])
  store.organizationDetails = {
    members: [{ id: 'owner' }, { id: 'member-1' }, { id: 'member-2' }],
  } as OrganizationDetails
  vi.spyOn(store, 'deleteOrganization')

  const wrapper = await confirmDeletion()

  expect(wrapper.text()).toContain('Remove the other 2 members')
  expect(wrapper.findAll('button')[2].attributes('disabled')).toBeDefined()
  expect(store.deleteOrganization).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('disables deleting the only organization', async () => {
  const store = selectFirstOf([{ id: 'organization-a', name: 'A' } as Organization])
  vi.spyOn(store, 'deleteOrganization')

  const wrapper = mountDelete()

  expect(wrapper.findAll('button')[0].attributes('disabled')).toBeDefined()
  expect(store.deleteOrganization).not.toHaveBeenCalled()
  wrapper.unmount()
})

it('allows deleting an organization when another one remains', async () => {
  selectFirstOf([
    { id: 'organization-a', name: 'A' } as Organization,
    { id: 'organization-b', name: 'B' } as Organization,
  ])

  const wrapper = mountDelete()

  expect(wrapper.findAll('button')[0].attributes('disabled')).toBeUndefined()
  wrapper.unmount()
})
