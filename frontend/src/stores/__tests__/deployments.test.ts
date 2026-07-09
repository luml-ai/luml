import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDeploymentsStore } from '@/stores/deployments'
import { api } from '@/lib/api'
import {
  DeploymentStatusEnum,
  MonitoringMode,
  type Deployment,
  type UpdateDeploymentPayload,
} from '@/lib/api/deployments/interfaces'

vi.mock('@/lib/api', () => ({
  api: {
    deployments: {
      update: vi.fn(),
    },
  },
}))

const mockApi = vi.mocked(api, true)

const ORG = 'org-1'
const ORBIT = 'orbit-1'
const DEPLOYMENT = 'dep-1'

function makeDeployment(overrides: Partial<Deployment> = {}): Deployment {
  return {
    id: DEPLOYMENT,
    orbit_id: ORBIT,
    satellite_id: 'sat-1',
    artifact_id: 'art-1',
    inference_url: '',
    status: DeploymentStatusEnum.active,
    monitoring_mode: MonitoringMode.off,
    secrets: {},
    created_by_user: 'user',
    tags: [],
    created_at: '',
    updated_at: '',
    satellite_name: 'sat',
    name: 'dep',
    description: '',
    collection_id: 'col-1',
    dynamic_attributes_secrets: {},
    artifact_name: 'model',
    error_message: null,
    schemas: {},
    ...overrides,
  }
}

describe('deployments store', () => {
  let store: ReturnType<typeof useDeploymentsStore>

  beforeEach(() => {
    setActivePinia(createPinia())
    store = useDeploymentsStore()
    vi.clearAllMocks()
  })

  it('update forwards monitoring_mode to the API and refreshes the list', async () => {
    const updated = makeDeployment({ monitoring_mode: MonitoringMode.full })
    store.setDeployments([makeDeployment()])
    mockApi.deployments.update.mockResolvedValue(updated)

    const payload: UpdateDeploymentPayload = {
      name: 'dep',
      description: '',
      tags: [],
      dynamic_attributes_secrets: {},
      monitoring_mode: MonitoringMode.full,
    }
    await store.update(ORG, ORBIT, DEPLOYMENT, payload)

    expect(mockApi.deployments.update).toHaveBeenCalledWith(ORG, ORBIT, DEPLOYMENT, payload)
    expect(store.deployments[0].monitoring_mode).toBe(MonitoringMode.full)
  })
})
