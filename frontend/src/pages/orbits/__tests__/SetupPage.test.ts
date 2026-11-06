import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import SetupPage from '../SetupPage.vue'

vi.mock('vue-router', () => ({
  useRoute: () => ({ query: { tab: 'flow' }, fullPath: '/setup?tab=flow' }),
  useRouter: () => ({ replace: vi.fn(), push: vi.fn() }),
}))
const state = vi.hoisted(() => ({
  isAuth: false,
  currentOrganization: null as { id: string; permissions: { orbit: string[] } } | null,
}))

vi.mock('@/stores/auth', () => ({
  useAuthStore: () => ({
    get isAuth() {
      return state.isAuth
    },
  }),
}))
vi.mock('@/stores/organization', () => ({
  useOrganizationStore: () => ({
    get currentOrganization() {
      return state.currentOrganization
    },
  }),
}))
vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => ({ orbitsList: [] }) }))

beforeEach(() => {
  state.isAuth = false
  state.currentOrganization = null
})

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

describe('SetupPage first card', () => {
  async function firstCard(orbitPermissions: string[]) {
    state.isAuth = true
    state.currentOrganization = { id: 'organization-a', permissions: { orbit: orbitPermissions } }
    const wrapper = mount(SetupPage, {
      global: { stubs: { DButton: true, OrbitCreator: true, UiPageLoader: true } },
    })
    await flushPromises()
    return wrapper.findAll('.card')[0]!
  }

  it('offers to create an orbit to members who can create one', async () => {
    const card = await firstCard(['list', 'create'])

    expect(card.find('.title').text()).toBe('Create an Orbit')
    expect(card.find('.actions').exists()).toBe(true)
  })

  it('offers to create an orbit when there is no organization', async () => {
    state.isAuth = true
    const wrapper = mount(SetupPage, {
      global: { stubs: { DButton: true, OrbitCreator: true, UiPageLoader: true } },
    })
    await flushPromises()

    expect(wrapper.findAll('.card')[0]!.find('.title').text()).toBe('Create an Orbit')
  })

  it('asks members who cannot create orbits to be added to one', async () => {
    const card = await firstCard(['list'])

    expect(card.find('.title').text()).toBe('No orbits yet')
    expect(card.text()).toContain('add you to an orbit')
    expect(card.find('.actions').exists()).toBe(false)
  })
})
