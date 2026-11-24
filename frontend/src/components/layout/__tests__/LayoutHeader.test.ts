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
vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('@/lib/api', () => ({ api: { readOwnershipTransferNotices: mocks.read } }))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isAuth: true }) }))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({
    currentOrganization: { id: 'example' },
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
})
it('shows the previous owner the result once and refreshes their role without navigation', async () => {
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
  route.fullPath = '/organization/example/orbits'
  await flushPromises()
  expect(mocks.toast).toHaveBeenCalledOnce()
  expect(mocks.refreshDetails).toHaveBeenCalledOnce()
  expect(route.fullPath).toBe('/organization/example/orbits')
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
