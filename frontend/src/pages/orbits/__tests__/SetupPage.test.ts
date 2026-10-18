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
  it('shows the local card before the relayed card, and commands only on the local card', async () => {
    const wrapper = mount(SetupPage, {
      global: { stubs: { DButton: true, OrbitCreator: true, UiPageLoader: true } },
    })
    await flushPromises()

    expect(wrapper.get('.page-header__title').text()).toBe('Flow')
    const cards = wrapper.findAll('.card')
    expect(cards.map((card) => card.find('.title').text())).toEqual([
      'Get Started',
      'Local flow',
      'Relayed flow',
    ])
    expect(cards[1]!.findAll('.command-code').map((code) => code.text())).toEqual([
      'pip install lumlflow',
      'lumlflow ui',
    ])
    expect(cards[2]!.find('.commands').exists()).toBe(false)
  })

  it('points to the docs page for exposing a flow instead of building a relay command', async () => {
    const wrapper = mount(SetupPage, {
      global: { stubs: { DButton: true, OrbitCreator: true, UiPageLoader: true } },
    })
    await flushPromises()

    const docsLink = wrapper.get('a.link')
    expect(docsLink.attributes('href')).toMatch(/\/apps\/lumlflow\/relayed_flows$/)
    expect(docsLink.attributes('target')).toBe('_blank')
    expect(wrapper.text()).not.toContain('luml-relay')
  })
})
