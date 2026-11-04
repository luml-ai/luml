import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { reactive } from 'vue'
import { createMemoryHistory, createRouter } from 'vue-router'
import OrbitDeploymentsView from './OrbitDeploymentsView.vue'
import OrbitSecretsView from './OrbitSecretsView.vue'

const authStore = reactive({ isAuth: true })
const deploymentsStore = reactive({
  deployments: [],
  creatorVisible: false,
  getDeployments: vi.fn().mockResolvedValue([]),
  setDeployments: vi.fn(),
  reset: vi.fn(),
  showCreator: vi.fn(),
})
const secretsStore = reactive({
  creatorVisible: false,
  loadSecrets: vi.fn().mockResolvedValue(undefined),
  showCreator: vi.fn(() => {
    secretsStore.creatorVisible = true
  }),
  hideCreator: vi.fn(),
})

vi.mock('@/stores/auth', () => ({ useAuthStore: () => authStore }))
vi.mock('@/stores/deployments', () => ({ useDeploymentsStore: () => deploymentsStore }))
vi.mock('@/stores/orbit-secrets', () => ({ useSecretsStore: () => secretsStore }))
vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({ currentOrbitDetails: { organization_id: 'org-1', id: 'orbit-1' } }),
}))
vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

async function mountRoute(name = 'orbit-secrets') {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      {
        path: '/organization/:organizationId/orbit/:id/deployments',
        name: 'orbit-deployments',
        component: OrbitDeploymentsView,
      },
      {
        path: '/organization/:organizationId/orbit/:id/secrets',
        name: 'orbit-secrets',
        component: OrbitSecretsView,
      },
    ],
  })
  await router.push({ name, params: { organizationId: 'org-1', id: 'orbit-1' } })
  await router.isReady()
  const wrapper = mount(
    { template: '<router-view />' },
    {
      global: {
        plugins: [router],
        stubs: {
          'd-button': {
            props: ['label'],
            template: '<button>{{ label }}</button>',
          },
          DeploymentsTable: true,
          DeploymentsCreateModal: true,
          UiCardAdd: true,
          SecretsList: true,
          SecretCreator: true,
        },
      },
    },
  )
  await flushPromises()
  return { wrapper, router }
}

describe('orbit secrets navigation', () => {
  beforeEach(() => {
    authStore.isAuth = true
    secretsStore.creatorVisible = false
  })

  it('keeps secret creation and return navigation after opening the Secrets tab', async () => {
    const { wrapper, router } = await mountRoute('orbit-deployments')
    await wrapper.findAll('button.tab')[1].trigger('click')
    await flushPromises()

    expect(router.currentRoute.value.name).toBe('orbit-secrets')
    expect(wrapper.get('.tab.active').text()).toBe('Secrets')
    const createButton = wrapper.get('.page-header button')
    expect(createButton.text()).toBe('Create secret')
    await createButton.trigger('click')
    expect(secretsStore.showCreator).toHaveBeenCalledOnce()
    expect(wrapper.getComponent({ name: 'SecretCreator' }).props('visible')).toBe(true)

    await wrapper.findAll('button.tab')[0].trigger('click')
    await flushPromises()
    expect(router.currentRoute.value.name).toBe('orbit-deployments')
    expect(wrapper.get('.tab.active').text()).toBe('Deployments')
    expect(wrapper.text()).toContain('Create deployment')
    wrapper.unmount()
  })

  it('loads secrets using the deep-linked route and reloads after an orbit change', async () => {
    const { wrapper, router } = await mountRoute()
    expect(secretsStore.loadSecrets).toHaveBeenCalledWith('org-1', 'orbit-1')
    expect(wrapper.get('.tab.active').text()).toBe('Secrets')

    await router.push({
      name: 'orbit-secrets',
      params: { organizationId: 'org-2', id: 'orbit-2' },
    })
    await flushPromises()

    expect(secretsStore.loadSecrets).toHaveBeenLastCalledWith('org-2', 'orbit-2')
    expect(wrapper.getComponent({ name: 'SecretCreator' }).props()).toMatchObject({
      organizationId: 'org-2',
      orbitId: 'orbit-2',
    })
    expect(wrapper.get('.tab.active').text()).toBe('Secrets')
    wrapper.unmount()
  })

  it('hides the secret creation action for unauthenticated users', async () => {
    authStore.isAuth = false
    const { wrapper } = await mountRoute()
    expect(wrapper.text()).not.toContain('Create secret')
    expect(wrapper.findAll('button.tab')).toHaveLength(2)
    wrapper.unmount()
  })
})
