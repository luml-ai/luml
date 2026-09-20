import { flushPromises, mount } from '@vue/test-utils'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Deployment } from '@/lib/api/deployments/interfaces'
import DeploymentSchemaPage from './DeploymentSchemaPage.vue'

const deploymentsStore = {
  getDeployment: vi.fn(),
}

const satellitesStore = {
  getSatellite: vi.fn(),
}

vi.mock('vue-router', () => ({
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
  return mount(DeploymentSchemaPage, {
    global: {
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
