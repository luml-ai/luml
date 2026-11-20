import { mount } from '@vue/test-utils'
import { describe, expect, it, vi, beforeEach } from 'vitest'
import { nextTick, reactive } from 'vue'
import { createMemoryHistory, createRouter, type RouteRecordRaw } from 'vue-router'
import appRouter from '@/router'
import LayoutSidebar from '../LayoutSidebar.vue'

const ORG = '0199c50e-57ac-7823-b010-d5473e5eead1'
const ORBIT = '0199c8cf-4d35-783b-9f81-cb3cec788074'

const route = reactive({
  name: 'home' as string,
  query: {} as Record<string, string>,
  meta: {} as Record<string, unknown>,
  matched: [] as { name?: string | symbol }[],
})
const organizationStore = reactive({ currentOrganization: null as { id: string } | null })
const orbitsStore = reactive({ currentOrbitId: null as string | null })

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: () => route,
}))
vi.mock('@/router/middlewares', () => ({ installMiddlewares: vi.fn() }))
vi.mock('@/pages/HomePage.vue', () => ({ default: { template: '<div />' } }))
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
    route.meta = {}
    route.matched = []
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

describe('LayoutSidebar GitHub entry', () => {
  it('links to the luml repository', () => {
    const link = mountSidebar().get('a.menu-link--github')

    expect(link.attributes('href')).toBe('https://github.com/luml-ai/luml')
  })
})

// use the production route tree without loading page components or authentication
function testRoutes(routes: readonly RouteRecordRaw[]): RouteRecordRaw[] {
  return routes.map((route) => ({
    ...route,
    ...(route.component ? { component: { template: '<router-view />' } } : {}),
    ...(route.children ? { children: testRoutes(route.children) } : {}),
  })) as RouteRecordRaw[]
}

const orbitPath = `/organization/${ORG}/orbit/${ORBIT}`
const collectionPath = `${orbitPath}/collection/${ORG}`
const artifactPath = `${collectionPath}/artifacts/${ORBIT}`

const sidebarPages = [
  ['/express-tasks', 'Express tasks'],
  ['/express-tasks/classification', 'Express tasks'],
  ['/express-tasks/regression', 'Express tasks'],
  ['/express-tasks/forecasting', 'Express tasks'],
  ['/express-tasks/runtime', 'Express tasks'],
  ['/express-tasks/prompt-fusion', 'Express tasks'],
  ['/express-tasks/prompt-fusion/edit', 'Express tasks'],
  ['/express-tasks/notebooks', 'Express tasks'],
  [orbitPath, 'Registry'],
  [`${orbitPath}/tracks`, 'Registry'],
  [`${orbitPath}/tracks/${ORG}`, 'Registry'],
  [collectionPath, 'Registry'],
  [`${collectionPath}/compare`, 'Registry'],
  [artifactPath, 'Registry'],
  ...['data', 'card', 'experiment-snapshot', 'attachments', 'lineage'].map((tab) => [
    `${artifactPath}/${tab}`,
    'Registry',
  ]),
  [`${orbitPath}/deployments`, 'Deployments'],
  [`${orbitPath}/secrets`, 'Deployments'],
  [`${orbitPath}/deployments/${ORG}/schema`, 'Deployments'],
  [`${orbitPath}/deployments/${ORG}/monitoring`, 'Deployments'],
  [`${orbitPath}/satellites`, 'Satellites'],
  [`${orbitPath}/flow`, 'Flow'],
  ['/prisma', 'Prisma'],
  ['/prisma/repos', 'Prisma'],
  ['/prisma/tasks/task-id', 'Prisma'],
  ['/prisma/runs/run-id', 'Prisma'],
]

describe('LayoutSidebar subpage selection', () => {
  beforeEach(() => {
    organizationStore.currentOrganization = { id: ORG }
    orbitsStore.currentOrbitId = ORBIT
    route.name = 'home'
    route.query = {}
    route.meta = {}
    route.matched = []
  })

  it.each(sidebarPages)('selects the parent on a direct visit to %s', (path, label) => {
    Object.assign(route, appRouter.resolve(path))
    const wrapper = mountSidebar()

    expect(wrapper.findAll('a.active').map((link) => link.text())).toEqual([label])
    wrapper.unmount()
  })

  it('updates the selection when navigating and going back and forward', async () => {
    const router = createRouter({
      history: createMemoryHistory(),
      routes: testRoutes(appRouter.options.routes),
    })
    const removeHook = router.afterEach((to) => Object.assign(route, to))
    await router.push('/express-tasks/classification')
    const wrapper = mountSidebar()
    const selected = () => wrapper.findAll('a.active').map((link) => link.text())
    const travel = async (direction: 'back' | 'forward') => {
      await new Promise<void>((resolve) => {
        const remove = router.afterEach(() => {
          remove()
          resolve()
        })
        router[direction]()
      })
      await nextTick()
    }

    expect(selected()).toEqual(['Express tasks'])
    await router.push(`${artifactPath}/data`)
    expect(selected()).toEqual(['Registry'])
    await router.push('/prisma/repos')
    expect(selected()).toEqual(['Prisma'])
    await travel('back')
    expect(selected()).toEqual(['Registry'])
    await travel('back')
    expect(selected()).toEqual(['Express tasks'])
    await travel('forward')
    expect(selected()).toEqual(['Registry'])
    removeHook()
    wrapper.unmount()
  })

  it.each(['/', '/sign-in', '/unknown-page', `/organization/${ORG}`])(
    'does not select an unrelated section at %s',
    (path) => {
      Object.assign(route, appRouter.resolve(path))
      const wrapper = mountSidebar()

      expect(wrapper.findAll('a.active')).toHaveLength(0)
      wrapper.unmount()
    },
  )

  it.each([
    ['registry', 'Registry'],
    ['deployments', 'Deployments'],
    ['satellites', 'Satellites'],
    ['flow', 'Flow'],
  ])('preserves the %s setup tab selection', (tab, label) => {
    Object.assign(route, appRouter.resolve({ name: 'setup', query: { tab } }))
    const wrapper = mountSidebar()

    expect(wrapper.findAll('a.active').map((link) => link.text())).toEqual([label])
    wrapper.unmount()
  })
})
