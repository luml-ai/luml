import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import axios, { type AxiosResponse } from 'axios'
import { api } from '@/lib/api'
import {
  ArtifactStatusEnum,
  ArtifactTypeEnum,
  type Artifact,
  type ArtifactDeleteFailure,
  type ArtifactDeleteReason,
  type ArtifactDeleteUrl,
} from '@/lib/api/artifacts/interfaces'
import { DeploymentStatusEnum } from '@/lib/api/deployments/interfaces'
import { useArtifactsStore } from '@/stores/artifacts'

vi.mock('vue-router', () => ({
  useRoute: () => ({
    params: {
      organizationId: 'org-1',
      id: 'orbit-1',
      collectionId: 'collection-1',
    },
  }),
}))

vi.mock('@/lib/api', () => ({
  api: {
    artifacts: {
      requestDeleteUrls: vi.fn(),
      confirmDelete: vi.fn(),
      update: vi.fn(),
    },
  },
}))

vi.mock('axios', () => ({
  default: {
    delete: vi.fn(),
  },
}))

const mockApi = vi.mocked(api, true)
const mockBucketDelete = vi.mocked(axios.delete)

const ORG = 'org-1'
const ORBIT = 'orbit-1'
const COLLECTION = 'collection-1'

function makeArtifact(id: string, overrides: Partial<Artifact> = {}): Artifact {
  return {
    id,
    type: ArtifactTypeEnum.model,
    collection_id: COLLECTION,
    collection_name: 'Models',
    file_name: `${id}.zip`,
    name: id,
    description: '',
    extra_values: {},
    manifest: {} as Artifact['manifest'],
    file_hash: '',
    file_index: {},
    bucket_location: id,
    size: 1,
    unique_identifier: id,
    status: ArtifactStatusEnum.uploaded,
    created_at: '',
    updated_at: '',
    deployments: [],
    tracks: [],
    ...overrides,
  }
}

function makeDeleteUrl(id: string, name = id): ArtifactDeleteUrl {
  return {
    artifact_id: id,
    name,
    url: `https://bucket.example/${id}`,
  }
}

function makeFailure(
  id: string,
  reason: ArtifactDeleteReason,
  overrides: Partial<ArtifactDeleteFailure> = {},
): ArtifactDeleteFailure {
  return {
    artifact_id: id,
    name: id,
    reason,
    deployments: [],
    tracks: [],
    ...overrides,
  }
}

function bucketResponse(status: number): AxiosResponse {
  return { status } as AxiosResponse
}

describe('artifacts store', () => {
  let store: ReturnType<typeof useArtifactsStore>

  beforeEach(() => {
    vi.resetAllMocks()
    setActivePinia(createPinia())
    store = useArtifactsStore()
  })

  it('runs all three phases and removes deleted artifacts from the list', async () => {
    const ids = ['artifact-a', 'artifact-b', 'artifact-c']
    store.setArtifactsList(ids.map((id) => makeArtifact(id)))
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({
      urls: ids.map((id) => makeDeleteUrl(id)),
      failed: [],
    })
    mockBucketDelete.mockResolvedValue(bucketResponse(204))
    mockApi.artifacts.confirmDelete.mockResolvedValueOnce({ deleted: ids, failed: [] })

    const result = await store.deleteArtifacts(ids)

    expect(result).toEqual({ deleted: ids, failed: [] })
    expect(mockApi.artifacts.requestDeleteUrls).toHaveBeenCalledWith(ORG, ORBIT, COLLECTION, ids)
    expect(mockBucketDelete.mock.calls.map(([url]) => url)).toEqual(
      ids.map((id) => `https://bucket.example/${id}`),
    )
    expect(mockApi.artifacts.confirmDelete).toHaveBeenCalledWith(ORG, ORBIT, COLLECTION, ids)
    expect(store.artifactsList).toEqual([])
  })

  it('merges failures from the request, bucket, and confirmation phases', async () => {
    const ids = ['artifact-a', 'artifact-b', 'artifact-c']
    const deploymentFailure = makeFailure('artifact-b', 'deployments', {
      deployments: [{ id: 'deployment-1', name: 'stuck', status: DeploymentStatusEnum.failed }],
    })
    const trackFailure = makeFailure('artifact-c', 'tracks', {
      tracks: [{ id: 'track-1', name: 'release' }],
    })
    store.setArtifactsList(ids.map((id) => makeArtifact(id)))
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({
      urls: [makeDeleteUrl('artifact-a', 'A'), makeDeleteUrl('artifact-c', 'C')],
      failed: [deploymentFailure],
    })
    mockBucketDelete.mockImplementation((url) =>
      url.endsWith('artifact-a')
        ? Promise.reject({ response: { status: 500 } })
        : Promise.resolve(bucketResponse(204)),
    )
    mockApi.artifacts.update.mockResolvedValueOnce(
      makeArtifact('artifact-a', { status: ArtifactStatusEnum.deletion_failed }),
    )
    mockApi.artifacts.confirmDelete.mockResolvedValueOnce({
      deleted: [],
      failed: [trackFailure],
    })

    const result = await store.deleteArtifacts(ids)

    expect(result).toEqual({
      deleted: [],
      failed: [
        deploymentFailure,
        makeFailure('artifact-a', 'storage_error', { name: 'A' }),
        trackFailure,
      ],
    })
    expect(mockApi.artifacts.confirmDelete).toHaveBeenCalledWith(ORG, ORBIT, COLLECTION, [
      'artifact-c',
    ])
    expect(store.artifactsList.find(({ id }) => id === 'artifact-a')?.status).toBe(
      ArtifactStatusEnum.deletion_failed,
    )
    expect(store.artifactsList.find(({ id }) => id === 'artifact-b')?.status).toBe(
      ArtifactStatusEnum.uploaded,
    )
    expect(store.artifactsList.find(({ id }) => id === 'artifact-c')?.status).toBe(
      ArtifactStatusEnum.pending_deletion,
    )
  })

  it('treats a bucket 404 as a successful deletion', async () => {
    store.setArtifactsList([makeArtifact('artifact-a')])
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({
      urls: [makeDeleteUrl('artifact-a')],
      failed: [],
    })
    mockBucketDelete.mockRejectedValueOnce({ response: { status: 404 } })
    mockApi.artifacts.confirmDelete.mockResolvedValueOnce({
      deleted: ['artifact-a'],
      failed: [],
    })

    const result = await store.deleteArtifacts(['artifact-a'])

    expect(result.deleted).toEqual(['artifact-a'])
    expect(mockApi.artifacts.confirmDelete).toHaveBeenCalledWith(ORG, ORBIT, COLLECTION, [
      'artifact-a',
    ])
  })

  it('sets deletion_failed after a bucket failure and carries the URL entry name', async () => {
    store.setArtifactsList([makeArtifact('artifact-a', { name: 'Original name' })])
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({
      urls: [makeDeleteUrl('artifact-a', 'Platform name')],
      failed: [],
    })
    mockBucketDelete.mockResolvedValueOnce(bucketResponse(403))
    mockApi.artifacts.update.mockResolvedValueOnce(
      makeArtifact('artifact-a', { status: ArtifactStatusEnum.deletion_failed }),
    )

    const result = await store.deleteArtifacts(['artifact-a'])

    expect(mockApi.artifacts.update).toHaveBeenCalledWith(ORG, ORBIT, COLLECTION, 'artifact-a', {
      id: 'artifact-a',
      status: ArtifactStatusEnum.deletion_failed,
    })
    expect(result).toEqual({
      deleted: [],
      failed: [makeFailure('artifact-a', 'storage_error', { name: 'Platform name' })],
    })
    expect(store.artifactsList[0].status).toBe(ArtifactStatusEnum.deletion_failed)
    expect(mockApi.artifacts.confirmDelete).not.toHaveBeenCalled()
  })

  it('keeps going when the deletion_failed status update fails', async () => {
    const updateError = new Error('update failed')
    const consoleError = vi.spyOn(console, 'error').mockImplementation(() => undefined)
    store.setArtifactsList([makeArtifact('artifact-a')])
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({
      urls: [makeDeleteUrl('artifact-a')],
      failed: [],
    })
    mockBucketDelete.mockRejectedValueOnce(new Error('bucket unavailable'))
    mockApi.artifacts.update.mockRejectedValueOnce(updateError)

    const result = await store.deleteArtifacts(['artifact-a'])

    expect(result.failed).toEqual([makeFailure('artifact-a', 'storage_error')])
    expect(result.error).toBeUndefined()
    expect(store.artifactsList[0].status).toBe(ArtifactStatusEnum.pending_deletion)
    expect(consoleError).toHaveBeenCalledWith(
      'Failed to set artifact artifact-a status to deletion_failed',
      updateError,
    )
    expect(mockApi.artifacts.confirmDelete).not.toHaveBeenCalled()
  })

  it('reflects a signing storage error in the local list', async () => {
    const failure = makeFailure('artifact-a', 'storage_error')
    store.setArtifactsList([makeArtifact('artifact-a')])
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({ urls: [], failed: [failure] })

    const result = await store.deleteArtifacts(['artifact-a'])

    expect(result.failed).toEqual([failure])
    expect(store.artifactsList[0].status).toBe(ArtifactStatusEnum.deletion_failed)
    expect(mockBucketDelete).not.toHaveBeenCalled()
    expect(mockApi.artifacts.update).not.toHaveBeenCalled()
  })

  it('removes not_found rows without returning them as dialog failures', async () => {
    const ids = ['artifact-a', 'artifact-b']
    store.setArtifactsList(ids.map((id) => makeArtifact(id)))
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({
      urls: [makeDeleteUrl('artifact-a')],
      failed: [makeFailure('artifact-b', 'not_found', { name: null })],
    })
    mockBucketDelete.mockResolvedValueOnce(bucketResponse(204))
    mockApi.artifacts.confirmDelete.mockResolvedValueOnce({
      deleted: [],
      failed: [makeFailure('artifact-a', 'not_found', { name: null })],
    })

    const result = await store.deleteArtifacts(ids)

    expect(result).toEqual({ deleted: [], failed: [] })
    expect(store.artifactsList).toEqual([])
  })

  it('collapses duplicates before making requests', async () => {
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({ urls: [], failed: [] })

    await store.deleteArtifacts(['artifact-a', 'artifact-b', 'artifact-a'])

    expect(mockApi.artifacts.requestDeleteUrls).toHaveBeenCalledOnce()
    expect(mockApi.artifacts.requestDeleteUrls).toHaveBeenCalledWith(ORG, ORBIT, COLLECTION, [
      'artifact-a',
      'artifact-b',
    ])
  })

  it('processes chunks sequentially and merges their list updates', async () => {
    const ids = Array.from({ length: 130 }, (_, index) => `artifact-${index}`)
    store.setArtifactsList(ids.map((id) => makeArtifact(id)))
    mockApi.artifacts.requestDeleteUrls.mockImplementation(
      async (_organizationId, _orbitId, _collectionId, artifactIds) => ({
        urls: artifactIds.map((id) => makeDeleteUrl(id)),
        failed: [],
      }),
    )
    mockBucketDelete.mockResolvedValue(bucketResponse(204))
    mockApi.artifacts.confirmDelete.mockImplementation(
      async (_organizationId, _orbitId, _collectionId, artifactIds) => ({
        deleted: artifactIds,
        failed: [],
      }),
    )

    const result = await store.deleteArtifacts(ids)

    expect(mockApi.artifacts.requestDeleteUrls).toHaveBeenCalledTimes(2)
    expect(mockApi.artifacts.requestDeleteUrls.mock.calls[0][3]).toHaveLength(100)
    expect(mockApi.artifacts.requestDeleteUrls.mock.calls[1][3]).toHaveLength(30)
    expect(mockApi.artifacts.confirmDelete).toHaveBeenCalledTimes(2)
    expect(mockApi.artifacts.confirmDelete.mock.calls[0][3]).toHaveLength(100)
    expect(mockApi.artifacts.confirmDelete.mock.calls[1][3]).toHaveLength(30)
    expect(mockApi.artifacts.confirmDelete.mock.invocationCallOrder[0]).toBeLessThan(
      mockApi.artifacts.requestDeleteUrls.mock.invocationCallOrder[1],
    )
    expect(result).toEqual({ deleted: ids, failed: [] })
    expect(store.artifactsList).toEqual([])
  })

  it('stops after a later request error and reports only unfinished ids', async () => {
    const ids = Array.from({ length: 230 }, (_, index) => `artifact-${index}`)
    const error = new Error('request failed')
    store.setArtifactsList(ids.map((id) => makeArtifact(id)))
    mockApi.artifacts.requestDeleteUrls
      .mockResolvedValueOnce({
        urls: ids.slice(0, 100).map((id) => makeDeleteUrl(id)),
        failed: [],
      })
      .mockRejectedValueOnce(error)
    mockBucketDelete.mockResolvedValue(bucketResponse(204))
    mockApi.artifacts.confirmDelete.mockResolvedValueOnce({
      deleted: ids.slice(0, 100),
      failed: [],
    })

    const result = await store.deleteArtifacts(ids)

    expect(result).toEqual({
      deleted: ids.slice(0, 100),
      failed: [],
      error,
      notCompleted: ids.slice(100),
    })
    expect(mockApi.artifacts.requestDeleteUrls).toHaveBeenCalledTimes(2)
    expect(mockApi.artifacts.confirmDelete).toHaveBeenCalledOnce()
    expect(store.artifactsList.map(({ id }) => id)).toEqual(ids.slice(100))
  })

  it('keeps classified failures when confirmation fails and retries only unknown outcomes', async () => {
    const error = new Error('confirmation failed')
    const deploymentFailure = makeFailure('artifact-b', 'deployments', {
      deployments: [{ id: 'deployment-1', name: 'api', status: DeploymentStatusEnum.active }],
    })
    const ids = ['artifact-a', 'artifact-b', 'artifact-c']
    store.setArtifactsList(ids.map((id) => makeArtifact(id)))
    mockApi.artifacts.requestDeleteUrls.mockResolvedValueOnce({
      urls: [makeDeleteUrl('artifact-a'), makeDeleteUrl('artifact-c')],
      failed: [deploymentFailure],
    })
    mockBucketDelete.mockResolvedValue(bucketResponse(204))
    mockApi.artifacts.confirmDelete.mockRejectedValueOnce(error)

    const result = await store.deleteArtifacts(ids)

    expect(result).toEqual({
      deleted: [],
      failed: [deploymentFailure],
      error,
      notCompleted: ['artifact-a', 'artifact-c'],
    })
    expect(store.artifactsList.find(({ id }) => id === 'artifact-a')?.status).toBe(
      ArtifactStatusEnum.pending_deletion,
    )
    expect(store.artifactsList.find(({ id }) => id === 'artifact-b')?.status).toBe(
      ArtifactStatusEnum.uploaded,
    )
    expect(store.artifactsList.find(({ id }) => id === 'artifact-c')?.status).toBe(
      ArtifactStatusEnum.pending_deletion,
    )
  })

  it('force deletion sends only chunked confirmations with force enabled', async () => {
    const ids = Array.from({ length: 130 }, (_, index) => `artifact-${index}`)
    store.setArtifactsList(ids.map((id) => makeArtifact(id)))
    mockApi.artifacts.confirmDelete.mockImplementation(
      async (_organizationId, _orbitId, _collectionId, artifactIds) => ({
        deleted: artifactIds,
        failed: [],
      }),
    )

    const result = await store.forceDeleteArtifacts(ids)

    expect(result).toEqual({ deleted: ids, failed: [] })
    expect(mockApi.artifacts.confirmDelete).toHaveBeenCalledTimes(2)
    expect(mockApi.artifacts.confirmDelete.mock.calls[0]).toEqual([
      ORG,
      ORBIT,
      COLLECTION,
      ids.slice(0, 100),
      true,
    ])
    expect(mockApi.artifacts.confirmDelete.mock.calls[1]).toEqual([
      ORG,
      ORBIT,
      COLLECTION,
      ids.slice(100),
      true,
    ])
    expect(mockApi.artifacts.requestDeleteUrls).not.toHaveBeenCalled()
    expect(mockBucketDelete).not.toHaveBeenCalled()
    expect(mockApi.artifacts.update).not.toHaveBeenCalled()
    expect(store.artifactsList).toEqual([])
  })

  it('keeps force blockers and removes force not_found rows', async () => {
    const trackFailure = makeFailure('artifact-a', 'tracks', {
      tracks: [{ id: 'track-1', name: 'release' }],
    })
    store.setArtifactsList([makeArtifact('artifact-a'), makeArtifact('artifact-b')])
    mockApi.artifacts.confirmDelete.mockResolvedValueOnce({
      deleted: [],
      failed: [trackFailure, makeFailure('artifact-b', 'not_found', { name: null })],
    })

    const result = await store.forceDeleteArtifacts(['artifact-a', 'artifact-b'])

    expect(result).toEqual({ deleted: [], failed: [trackFailure] })
    expect(store.artifactsList.map(({ id }) => id)).toEqual(['artifact-a'])
  })
})
