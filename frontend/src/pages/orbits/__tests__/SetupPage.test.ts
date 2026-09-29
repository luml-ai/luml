import { flushPromises, mount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import SetupPage from '../SetupPage.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { tab: 'flow' }, fullPath: '/setup?tab=flow' }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))
vi.mock('@/stores/auth', () => ({ useAuthStore: () => ({ isAuth: false }) }))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({ currentOrganization: null }),
}))
vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => ({ orbitsList: [] }) }))

describe('SetupPage Flow tab', () => {
  it('shows the instructions for running lumlflow locally to a user who is not signed in', async () => {
    const wrapper = mount(SetupPage, {
      global: { stubs: { DButton: true, OrbitCreator: true, UiPageLoader: true } },
    })
    await flushPromises()

    expect(wrapper.get('.page-header__title').text()).toBe('Flow')
    expect(wrapper.text()).toContain('Get Started')
    expect(wrapper.text()).toContain('Run Flow locally')
    expect(wrapper.text()).toContain('pip install lumlflow')
    expect(wrapper.text()).toContain('lumlflow ui')
  })
})
