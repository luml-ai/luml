import type { AxiosInstance } from 'axios'
import { describe, expect, it, vi } from 'vitest'
import { LineageApi } from '..'
import type { LineageBatchIn, LineageEdge, LineageGraph } from '../interfaces'

const edge: LineageEdge = {
  id: 'edge-1',
  source: 'node-a',
  target: 'node-b',
  created_by_user: 'Ada Lovelace',
  created_via: 'ui',
  created_at: '2026-01-01T00:00:00Z',
}

const graph: LineageGraph = {
  nodes: [],
  edges: [edge],
  focal_artifact_id: 'artifact-a',
  depth: 3,
  truncated: false,
}

function setupApi() {
  const get = vi.fn().mockResolvedValue({ data: graph })
  const post = vi.fn().mockResolvedValue({ data: [edge] })
  const del = vi.fn().mockResolvedValue({ data: edge })
  const client = { get, post, delete: del } as unknown as AxiosInstance
  return { api: new LineageApi(client), get, post, del }
}

describe('LineageApi', () => {
  it('loads a graph at the requested depth', async () => {
    const { api, get } = setupApi()

    await expect(api.getGraph('org', 'orbit', 'artifact-a', 3)).resolves.toEqual(graph)
    expect(get).toHaveBeenCalledWith(
      '/v1/organizations/org/orbits/orbit/artifacts/artifact-a/lineage',
      { params: { depth: 3 } },
    )
  })

  it('loads the whole graph when no depth is given', async () => {
    const { api, get } = setupApi()

    await expect(api.getGraph('org', 'orbit', 'artifact-a')).resolves.toEqual(graph)
    expect(get).toHaveBeenCalledWith(
      '/v1/organizations/org/orbits/orbit/artifacts/artifact-a/lineage',
      { params: {} },
    )
  })

  it('creates and deletes links through orbit-scoped endpoints', async () => {
    const { api, post, del } = setupApi()

    await api.createLinks('org', 'orbit', 'source', ['target-a', 'target-b'])
    expect(post).toHaveBeenCalledWith(
      '/v1/organizations/org/orbits/orbit/artifacts/source/lineage',
      { target_artifact_ids: ['target-a', 'target-b'] },
    )

    await expect(api.deleteLink('org', 'orbit', 'source', 'edge-1')).resolves.toEqual(edge)
    expect(del).toHaveBeenCalledWith(
      '/v1/organizations/org/orbits/orbit/artifacts/source/lineage/edge-1',
    )
  })

  it('applies a batch at the orbit level', async () => {
    const { api, post } = setupApi()
    const changes: LineageBatchIn = { create: [], delete: [], positions: [] }
    post.mockResolvedValueOnce({ data: { created: [], deleted: [] } })

    await expect(api.applyChanges('org', 'orbit', changes)).resolves.toEqual({
      created: [],
      deleted: [],
    })
    expect(post).toHaveBeenCalledWith('/v1/organizations/org/orbits/orbit/lineage/batch', changes)
  })
})
