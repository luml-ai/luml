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
      batchAction: vi.fn(),
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

describe('deployment batch actions', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
  })

  it('updates only deployments whose stop request succeeded', async () => {
    const store = useDeploymentsStore()
    store.setDeployments([makeDeployment(), makeDeployment({ id: 'blocked' })])
    mockApi.deployments.batchAction.mockResolvedValue({
      succeeded: [DEPLOYMENT],
      failed: [
        {
          deployment_id: 'blocked',
          name: 'blocked',
          reason: 'already_pending',
          message: 'Already shutting down',
        },
      ],
    })
    const result = await store.batchAction(ORG, ORBIT, [DEPLOYMENT, 'blocked'], 'undeploy')
    expect(result.failed).toHaveLength(1)
    expect(store.deployments[0].status).toBe(DeploymentStatusEnum.deletion_pending)
    expect(store.deployments[1].status).toBe(DeploymentStatusEnum.active)
  })

  it('removes only successful deletions and deduplicates the selection', async () => {
    const store = useDeploymentsStore()
    store.setDeployments([makeDeployment(), makeDeployment({ id: 'blocked' })])
    mockApi.deployments.batchAction.mockResolvedValue({
      succeeded: [DEPLOYMENT],
      failed: [
        {
          deployment_id: 'blocked',
          name: 'blocked',
          reason: 'references',
          message: 'Still referenced',
        },
      ],
    })
    await store.batchAction(ORG, ORBIT, [DEPLOYMENT, 'blocked', DEPLOYMENT], 'delete')
    expect(mockApi.deployments.batchAction).toHaveBeenCalledWith(
      ORG,
      ORBIT,
      [DEPLOYMENT, 'blocked'],
      'delete',
    )
    expect(store.deployments.map(({ id }) => id)).toEqual(['blocked'])
  })

  it('covers selections larger than the batch limit and preserves uncertain results after a request failure', async () => {
    const store = useDeploymentsStore()
    const ids = Array.from({ length: 201 }, (_, index) => `dep-${index}`)
    mockApi.deployments.batchAction
      .mockResolvedValueOnce({ succeeded: ids.slice(0, 100), failed: [] })
      .mockRejectedValueOnce(new Error('Request failed'))
      .mockResolvedValueOnce({ succeeded: ids.slice(200), failed: [] })
    const result = await store.batchAction(ORG, ORBIT, ids, 'delete')
    expect(mockApi.deployments.batchAction.mock.calls.map((call) => call[2].length)).toEqual([
      100, 100, 1,
    ])
    expect(result.succeeded).toEqual([...ids.slice(0, 100), ids[200]])
    expect(result.failed.map(({ deployment_id }) => deployment_id)).toEqual(ids.slice(100, 200))
    expect(result.failed.every(({ message }) => message.includes('not confirmed'))).toBe(true)
  })
})
