import { enableAutoUnmount, flushPromises, mount, shallowMount } from '@vue/test-utils'
import { reactive } from 'vue'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import OrganizationRegistryTable from './registry/OrganizationRegistryTable.vue'
import OrganizationManagePopover from './OrganizationManagePopover.vue'
import OrganizationPage from '@/pages/organization/index.vue'
import OrbitsPage from '@/pages/orbits/index.vue'
import TracksView from '@/pages/orbits/TracksView.vue'

const mocks = vi.hoisted(() => ({
  toast: vi.fn(),
  buckets: vi.fn(),
  switchOrganization: vi.fn(),
  details: vi.fn(),
  loadOrbits: vi.fn(),
  tracks: vi.fn(),
  push: vi.fn(),
}))
const organizationStore = reactive({
  currentOrganization: { id: 'org', name: 'Organization', permissions: {} },
  availableOrganizations: [
    { id: 'org', name: 'Organization', role: 'admin' },
    { id: 'other', name: 'Other' },
  ],
  switchOrganization: mocks.switchOrganization,
  getOrganizationDetails: mocks.details,
  loading: false,
})
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))
vi.mock('@/stores/buckets', () => ({
  useBucketsStore: () => ({ buckets: [], getBuckets: mocks.buckets }),
}))
vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({ orbitsList: [], loadOrbitsList: mocks.loadOrbits }),
}))
vi.mock('@/hooks/useTracksList', () => ({
  useTracksList: () => ({
    getInitialPage: mocks.tracks,
    setRequestInfo: vi.fn(),
    tracksList: { value: [] },
    list: { value: [] },
    reset: vi.fn(),
  }),
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { id: 'org', organizationId: 'org' }, matched: [], name: 'orbits' }),
  useRouter: () => ({ push: mocks.push }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: mocks.toast }),
}))
enableAutoUnmount(afterEach)
beforeEach(() => {
  vi.resetAllMocks()
  mocks.push.mockResolvedValue(undefined)
})

describe('organization registry requests', () => {
  it('shows loading while the bucket request is pending and reports a failure', async () => {
    let reject!: (error: Error) => void
    mocks.buckets.mockReturnValue(
      new Promise((_, rejectRequest) => {
        reject = rejectRequest
      }),
    )
    const wrapper = shallowMount(OrganizationRegistryTable)
    await wrapper.vm.$nextTick()
    expect(wrapper.findComponent({ name: 'UiPageLoader' }).exists()).toBe(true)
    expect(wrapper.text()).not.toContain('No buckets created')
    reject(new Error('Buckets unavailable'))
    await flushPromises()
    expect(wrapper.findComponent({ name: 'UiPageLoader' }).exists()).toBe(false)
    expect(mocks.toast).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'Buckets unavailable' }),
    )
  })
})
it('reports an organization switch failure without navigating', async () => {
  mocks.switchOrganization.mockRejectedValue(new Error('Switch failed'))
  const wrapper = mount(OrganizationManagePopover, {
    global: {
      stubs: {
        'd-button': true,
        UiId: true,
        OrganizationLeavePopover: true,
        OrganizationCreator: true,
        Avatar: true,
        Dialog: true,
        Popover: { template: '<div><slot /></div>' },
      },
    },
  })
  await wrapper.findAll('button.menu-item')[1].trigger('click')
  await flushPromises()
  expect(mocks.toast).toHaveBeenCalledWith(
    expect.objectContaining({ severity: 'error', detail: 'Switch failed' }),
  )
  expect(mocks.push).not.toHaveBeenCalled()
})
it('catches the organization details request for the current organization', async () => {
  mocks.details.mockRejectedValue(new Error('Details unavailable'))
  shallowMount(OrganizationPage)
  await flushPromises()
  expect(mocks.toast).toHaveBeenCalledWith(expect.objectContaining({ severity: 'error' }))
})
it('names organization details when the orbits request succeeded', async () => {
  mocks.loadOrbits.mockResolvedValue([])
  mocks.details.mockRejectedValue({ response: { status: 500 } })
  shallowMount(OrbitsPage)
  await flushPromises()
  expect(mocks.toast).toHaveBeenCalledWith(
    expect.objectContaining({ severity: 'error', detail: 'Failed to load organization details' }),
  )
})
it('names tracks when their initial request fails', async () => {
  mocks.tracks.mockRejectedValue(new Error('Unavailable'))
  shallowMount(TracksView)
  await flushPromises()
  expect(mocks.toast).toHaveBeenCalledWith(
    expect.objectContaining({ severity: 'error', detail: 'Failed to load tracks' }),
  )
})
