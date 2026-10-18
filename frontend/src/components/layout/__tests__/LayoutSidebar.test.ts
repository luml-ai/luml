import { mount } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { reactive } from 'vue'
import LayoutSidebar from '../LayoutSidebar.vue'

const ORG = '0199c50e-57ac-7823-b010-d5473e5eead1'
const ORBIT = '0199c8cf-4d35-783b-9f81-cb3cec788074'

const route = reactive({ name: 'home' as string, query: {} as Record<string, string> })
const organizationStore = reactive({ currentOrganization: null as { id: string } | null })
const orbitsStore = reactive({ currentOrbitId: null as string | null })

vi.mock('vue-router', () => ({ useRoute: () => route }))
vi.mock('@/stores/organization', () => ({ useOrganizationStore: () => organizationStore }))
vi.mock('@/stores/orbits', () => ({ useOrbitsStore: () => orbitsStore }))
vi.mock('@/stores/theme', () => ({
  useThemeStore: () => ({ getCurrentTheme: 'light', changeTheme: vi.fn() }),
}))
vi.mock('@/hooks/useLayout', () => ({ useLayout: () => ({ headerSizes: { height: 0 } }) }))
vi.mock('@/lib/github/GitHubService', () => ({
  GitHubService: { getStarsCount: vi.fn().mockResolvedValue(0) },
}))
vi.mock('@/lib/analytics/AnalyticsService', () => ({
  AnalyticsService: { track: vi.fn() },
  AnalyticsTrackKeysEnum: {},
}))

function mountSidebar() {
  return mount(LayoutSidebar, {
    global: {
      directives: { tooltip: () => undefined },
      stubs: {
        RouterLink: {
          props: ['to'],
          template: '<a class="menu-link" :data-to="JSON.stringify(to)"><slot /></a>',
        },
        UiThemeToggle: true,
        DButton: true,
      },
    },
  })
}

function flowLink(wrapper: ReturnType<typeof mountSidebar>) {
  const link = wrapper.findAll('a.menu-link').find((a) => a.text() === 'Flow')
  if (!link) throw new Error('Flow entry not found')
  return link
}

describe('LayoutSidebar Flow entry', () => {
  beforeEach(() => {
    route.name = 'home'
    route.query = {}
    organizationStore.currentOrganization = null
    orbitsStore.currentOrbitId = null
  })

  it('opens the Flow page of the current orbit', () => {
    organizationStore.currentOrganization = { id: ORG }
    orbitsStore.currentOrbitId = ORBIT

    const link = flowLink(mountSidebar())

    expect(JSON.parse(link.attributes('data-to')!)).toEqual({
      name: 'orbit-flow',
      params: { organizationId: ORG, id: ORBIT },
    })
  })

  it('sends a user without an orbit to the Flow tab of the setup page', () => {
    const link = flowLink(mountSidebar())

    expect(JSON.parse(link.attributes('data-to')!)).toEqual({
      name: 'setup',
      query: { tab: 'flow' },
    })
  })

  it('is active on the Flow page', () => {
    organizationStore.currentOrganization = { id: ORG }
    orbitsStore.currentOrbitId = ORBIT
    route.name = 'orbit-flow'

    expect(flowLink(mountSidebar()).classes()).toContain('active')
  })

  it('is not active on another orbit page', () => {
    organizationStore.currentOrganization = { id: ORG }
    orbitsStore.currentOrbitId = ORBIT
    route.name = 'orbit-satellites'

    expect(flowLink(mountSidebar()).classes()).not.toContain('active')
  })

  it('is active on the Flow tab of the setup page', () => {
    route.name = 'setup'
    route.query = { tab: 'flow' }

    expect(flowLink(mountSidebar()).classes()).toContain('active')
  })
})
