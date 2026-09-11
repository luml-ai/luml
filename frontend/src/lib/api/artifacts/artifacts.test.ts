import { describe, expect, it, vi } from 'vitest'
import type { AxiosInstance } from 'axios'
import { ArtifactsApi } from './index'

const ORG = 'org-1'
const ORBIT = 'orbit-1'
const COLLECTION = 'collection-1'

function makeApi(response: unknown): {
  instance: AxiosInstance
  post: ReturnType<typeof vi.fn>
  deleteRequest: ReturnType<typeof vi.fn>
} {
  const post = vi.fn().mockResolvedValue({ data: response })
  const deleteRequest = vi.fn().mockResolvedValue({ data: response })
  const instance = { post, delete: deleteRequest } as unknown as AxiosInstance
  return { instance, post, deleteRequest }
}

describe('ArtifactsApi', () => {
  it('requests batch delete URLs from the collection endpoint', async () => {
    const artifactIds = ['artifact-a', 'artifact-b']
    const response = { urls: [], failed: [] }
    const { instance, post } = makeApi(response)

    const result = await new ArtifactsApi(instance).requestDeleteUrls(
      ORG,
      ORBIT,
      COLLECTION,
      artifactIds,
    )

    expect(post).toHaveBeenCalledWith(
      `/v1/organizations/${ORG}/orbits/${ORBIT}/collections/${COLLECTION}/artifacts/delete-urls`,
      { artifact_ids: artifactIds },
    )
    expect(result).toEqual(response)
  })

  it.each([false, true])('confirms batch deletion with force=%s in the body', async (force) => {
    const artifactIds = ['artifact-a', 'artifact-b']
    const response = { deleted: artifactIds, failed: [] }
    const { instance, deleteRequest } = makeApi(response)
    const artifactsApi = new ArtifactsApi(instance)

    const result = force
      ? await artifactsApi.confirmDelete(ORG, ORBIT, COLLECTION, artifactIds, true)
      : await artifactsApi.confirmDelete(ORG, ORBIT, COLLECTION, artifactIds)

    expect(deleteRequest).toHaveBeenCalledWith(
      `/v1/organizations/${ORG}/orbits/${ORBIT}/collections/${COLLECTION}/artifacts`,
      { data: { artifact_ids: artifactIds, force } },
    )
    expect(result).toEqual(response)
  })
})
