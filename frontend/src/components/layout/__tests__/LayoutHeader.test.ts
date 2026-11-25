import { flushPromises, shallowMount } from '@vue/test-utils'
import { reactive } from 'vue'
import { beforeEach, expect, it, vi } from 'vitest'
import LayoutHeader from '../LayoutHeader.vue'

const mocks = vi.hoisted(() => ({
  read: vi.fn(),
  refresh: vi.fn(),
  refreshDetails: vi.fn(),
  toast: vi.fn(),
}))
const route = reactive({ fullPath: '/organization/example' })
const organization = reactive({ currentOrganization: { id: 'example' } as { id: string } | null })
vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('@/lib/api', () => ({ api: { readOwnershipTransferNotices: mocks.read } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isAuth: true }) }))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({
    get currentOrganization() {
      return organization.currentOrganization
    },
    getAvailableOrganizations: mocks.refresh,
    getOrganizationDetails: mocks.refreshDetails,
  }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))

beforeEach(() => {
  vi.resetAllMocks()
  route.fullPath = '/organization/example'
  organization.currentOrganization = { id: 'example' }
})
it('shows the previous owner the result once and refreshes their role', async () => {
  mocks.read
    .mockResolvedValueOnce([
      { status: 'accepted', organization_name: 'Example', recipient_email: 'new@example.com' },
    ])
    .mockResolvedValue([])
  const wrapper = shallowMount(LayoutHeader, {
    global: { stubs: { RouterLink: true, 'd-button': true } },
  })
  await flushPromises()
  expect(mocks.toast).toHaveBeenCalledWith(
    expect.objectContaining({ detail: 'Ownership of Example was transferred to new@example.com' }),
  )
  expect(mocks.refresh).toHaveBeenCalledOnce()
  expect(mocks.refreshDetails).toHaveBeenCalledExactlyOnceWith('example')
  expect(mocks.toast).toHaveBeenCalledOnce()
  wrapper.unmount()
})

it('reads the notices once per organization instead of on every navigation', async () => {
  mocks.read.mockResolvedValue([])
  const wrapper = shallowMount(LayoutHeader, {
    global: { stubs: { RouterLink: true, 'd-button': true } },
  })
  await flushPromises()
  route.fullPath = '/organization/example/orbits'
  await flushPromises()
  route.fullPath = '/organization/example/orbits?tab=members'
  await flushPromises()
  expect(mocks.read).toHaveBeenCalledExactlyOnceWith('example')
  organization.currentOrganization = { id: 'other' }
  await flushPromises()
  expect(mocks.read).toHaveBeenCalledTimes(2)
  expect(mocks.read).toHaveBeenLastCalledWith('other')
  wrapper.unmount()
})

it('refreshes the closed transfer after a decline while staying in the organization', async () => {
  mocks.read.mockResolvedValue([
    { status: 'declined', organization_name: 'Example', recipient_email: 'new@example.com' },
  ])
  const wrapper = shallowMount(LayoutHeader, {
    global: { stubs: { RouterLink: true, 'd-button': true } },
  })
  await flushPromises()
  expect(mocks.toast).toHaveBeenCalledWith(
    expect.objectContaining({ detail: 'new@example.com declined the ownership transfer' }),
  )
  expect(mocks.refreshDetails).toHaveBeenCalledExactlyOnceWith('example')
  expect(route.fullPath).toBe('/organization/example')
  wrapper.unmount()
})

it('does not refresh organization details when there are no result notices', async () => {
  mocks.read.mockResolvedValue([])
  const wrapper = shallowMount(LayoutHeader, {
    global: { stubs: { RouterLink: true, 'd-button': true } },
  })
  await flushPromises()
  expect(mocks.refreshDetails).not.toHaveBeenCalled()
  expect(mocks.refresh).not.toHaveBeenCalled()
  expect(mocks.toast).not.toHaveBeenCalled()
  wrapper.unmount()
})
