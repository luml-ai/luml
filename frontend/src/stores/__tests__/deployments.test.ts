import { describe, it, expect, vi, beforeEach } from 'vitest'
import { setActivePinia, createPinia } from 'pinia'
import { useDeploymentsStore } from '@/stores/deployments'
import { api } from '@/lib/api'
import { useSatellitesStore } from '@/stores/satellites'
import { SatelliteStatusEnum, type Satellite } from '@/lib/api/satellites/interfaces'
import {
  DeploymentStatusEnum,
  MonitoringMode,
  type Deployment,
  type UpdateDeploymentPayload,
} from '@/lib/api/deployments/interfaces'

vi.mock('@/lib/api', () => ({
  api: {
    deployments: {
      create: vi.fn(),
      deleteDeployment: vi.fn(),
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

describe('deployment wake signals', () => {
  const fetchMock = vi.fn()
  const satellite = (overrides: Partial<Satellite> = {}): Satellite => ({
    id: 'sat-1',
    orbit_id: ORBIT,
    name: 'satellite',
    description: '',
    base_url: 'https://satellite.example/',
    paired: true,
    capabilities: {},
    present_capabilities: ['wake'],
    created_at: '',
    updated_at: '',
    last_seen_at: '',
    status: SatelliteStatusEnum.active,
    ...overrides,
  })

  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    vi.stubGlobal('fetch', fetchMock)
    fetchMock.mockResolvedValue(undefined)
    useSatellitesStore().setList([satellite()])
  })

  it.each(['create', 'update', 'delete'] as const)(
    'wakes after successful %s without headers or body',
    async (action) => {
      const store = useDeploymentsStore()
      const deployment = makeDeployment()
      store.setDeployments([deployment])
      mockApi.deployments.create.mockResolvedValue(deployment)
      mockApi.deployments.update.mockResolvedValue(deployment)
      mockApi.deployments.deleteDeployment.mockResolvedValue(deployment)
      if (action === 'create') {
        await store.createDeployment(ORG, ORBIT, {
          satellite_id: 'sat-1',
          artifact_id: 'art-1',
          name: 'dep',
          description: '',
          tags: [],
          dynamic_attributes_secrets: {},
          satellite_parameters: {},
          monitoring_mode: MonitoringMode.off,
          env_variables: {},
          env_variables_secrets: {},
        })
      } else if (action === 'update') {
        await store.update(ORG, ORBIT, DEPLOYMENT, {
          name: 'dep',
          description: '',
          tags: [],
          dynamic_attributes_secrets: {},
        })
      } else {
        await store.deleteDeployment(ORG, ORBIT, DEPLOYMENT)
      }
      expect(fetchMock).toHaveBeenCalledExactlyOnceWith('https://satellite.example/wake', {
        method: 'POST',
        mode: 'no-cors',
        keepalive: true,
      })
    },
  )

  it.each([{ present_capabilities: [] }, { base_url: null }])(
    'skips satellites without wake or a base URL',
    async (overrides) => {
      useSatellitesStore().setList([satellite(overrides)])
      mockApi.deployments.deleteDeployment.mockResolvedValue(makeDeployment())
      await useDeploymentsStore().deleteDeployment(ORG, ORBIT, DEPLOYMENT)
      expect(fetchMock).not.toHaveBeenCalled()
    },
  )

  it('wakes each distinct successful satellite once across batches', async () => {
    const store = useDeploymentsStore()
    const items = Array.from({ length: 102 }, (_, index) =>
      makeDeployment({
        id: `dep-${index}`,
        satellite_id: index === 101 ? 'sat-2' : 'sat-1',
      }),
    )
    useSatellitesStore().setList([satellite(), satellite({ id: 'sat-2' })])
    store.setDeployments(items)
    mockApi.deployments.batchAction
      .mockResolvedValueOnce({ succeeded: items.slice(0, 100).map(({ id }) => id), failed: [] })
      .mockResolvedValueOnce({ succeeded: items.slice(100).map(({ id }) => id), failed: [] })
    await store.batchAction(
      ORG,
      ORBIT,
      items.map(({ id }) => id),
      'delete',
    )
    expect(fetchMock).toHaveBeenCalledTimes(2)
    expect(store.deployments).toEqual([])
  })

  it.each(['reject', 'throw', 'pending'] as const)(
    'ignores a %s wake and updates the UI immediately',
    async (failure) => {
      if (failure === 'reject') fetchMock.mockRejectedValue(new Error('blocked'))
      if (failure === 'throw')
        fetchMock.mockImplementation(() => {
          throw new Error('blocked')
        })
      if (failure === 'pending') fetchMock.mockReturnValue(new Promise(() => {}))
      mockApi.deployments.deleteDeployment.mockResolvedValue(
        makeDeployment({ status: DeploymentStatusEnum.deletion_pending }),
      )
      const store = useDeploymentsStore()
      store.setDeployments([makeDeployment()])
      await store.deleteDeployment(ORG, ORBIT, DEPLOYMENT)
      expect(store.deployments[0].status).toBe(DeploymentStatusEnum.deletion_pending)
    },
  )

  it('sends nothing after failed task creation', async () => {
    mockApi.deployments.deleteDeployment.mockRejectedValue(new Error('failed'))
    await expect(useDeploymentsStore().deleteDeployment(ORG, ORBIT, DEPLOYMENT)).rejects.toThrow(
      'failed',
    )
    expect(fetchMock).not.toHaveBeenCalled()
  })
})
