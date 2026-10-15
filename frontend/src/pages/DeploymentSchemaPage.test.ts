import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import PrimeVue from 'primevue/config'
import { createMemoryHistory, createRouter } from 'vue-router'
import type { Deployment } from '@/lib/api/deployments/interfaces'
import DeploymentSchemaPage from './DeploymentSchemaPage.vue'

const deploymentsStore = {
  getDeployment: vi.fn(),
}

const satellitesStore = {
  getSatellite: vi.fn(),
}

vi.mock('vue-router', async (importOriginal) => ({
  ...(await importOriginal<typeof import('vue-router')>()),
  useRoute: () => ({
    params: { organizationId: 'org-1', id: 'orbit-1', deploymentId: 'deployment-1' },
  }),
}))

vi.mock('@/stores/deployments', () => ({
  useDeploymentsStore: () => deploymentsStore,
}))

vi.mock('@/stores/satellites', () => ({
  useSatellitesStore: () => satellitesStore,
}))

vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

function deployment(inferenceUrl: string): Deployment {
  return {
    id: 'deployment-1',
    orbit_id: 'orbit-1',
    satellite_id: 'satellite-1',
    artifact_id: 'artifact-1',
    inference_url: inferenceUrl,
    schemas: { openapi: '3.0.0' },
  } as Deployment
}

function mountPage() {
  const router = createRouter({
    history: createMemoryHistory(),
    routes: [
      { path: '/', component: { template: '<div />' } },
      {
        path: '/organization/:organizationId/orbit/:id/deployments',
        name: 'orbit-deployments',
        component: { template: '<div />' },
      },
    ],
  })
  return mount(DeploymentSchemaPage, {
    global: {
      plugins: [router, PrimeVue],
      stubs: {
        OpenApi: {
          props: ['content', 'serverUrl'],
          template: '<div data-testid="open-api" :data-server-url="serverUrl || undefined" />',
        },
        UiPageLoader: { template: '<div data-testid="loader" />' },
        Ui404: { template: '<div data-testid="not-found" />' },
      },
    },
  })
}

describe('DeploymentSchemaPage', () => {
  beforeEach(() => {
    deploymentsStore.getDeployment.mockReset()
    satellitesStore.getSatellite.mockReset()
  })

  it('links back to the deployments list while the schema is loading', async () => {
    deploymentsStore.getDeployment.mockReturnValue(new Promise(() => {}))
    const wrapper = mountPage()
    const link = wrapper.get('nav a')

    expect(link.text()).toBe('Deployments')
    expect(link.attributes('href')).toBe('/organization/org-1/orbit/orbit-1/deployments')
    expect(wrapper.get('nav').text()).toContain('API schema')
    await link.trigger('click')
    await flushPromises()
    expect(wrapper.vm.$router.currentRoute.value.name).toBe('orbit-deployments')
  })

  it('keeps the deployments link available when the schema cannot be loaded', async () => {
    deploymentsStore.getDeployment.mockRejectedValue(new Error('Unavailable'))
    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="not-found"]').exists()).toBe(true)
    expect(wrapper.get('nav a').attributes('href')).toBe(
      '/organization/org-1/orbit/orbit-1/deployments',
    )
  })

  it('uses an absolute serving address without a Satellite address', async () => {
    deploymentsStore.getDeployment.mockResolvedValue(
      deployment('https://inference.example.com/models/shared'),
    )

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.get('[data-testid="open-api"]').attributes('data-server-url')).toBe(
      'https://inference.example.com/models/shared',
    )
    expect(satellitesStore.getSatellite).not.toHaveBeenCalled()
  })

  it('joins a relative serving address to the Satellite address', async () => {
    deploymentsStore.getDeployment.mockResolvedValue(deployment('/deployments/deployment-1'))
    satellitesStore.getSatellite.mockResolvedValue({ base_url: 'https://sat.example.com/' })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.get('[data-testid="open-api"]').attributes('data-server-url')).toBe(
      'https://sat.example.com/deployments/deployment-1',
    )
  })

  it('renders the schema without a server when a relative address has no base', async () => {
    deploymentsStore.getDeployment.mockResolvedValue(deployment('/deployments/deployment-1'))
    satellitesStore.getSatellite.mockResolvedValue({ base_url: null })

    const wrapper = mountPage()
    await flushPromises()

    expect(wrapper.find('[data-testid="open-api"]').exists()).toBe(true)
    expect(wrapper.get('[data-testid="open-api"]').attributes('data-server-url')).toBeUndefined()
    expect(wrapper.find('[data-testid="not-found"]').exists()).toBe(false)
  })
})
