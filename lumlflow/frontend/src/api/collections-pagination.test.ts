import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { GetLumlCollectionsParams } from './api.interface'
import type { CollectionInfo } from '@/components/upload/upload.interface'
import { apiService } from './api.service'
import { api } from './client'
import { usePagination } from '@/hooks/usePagination'

vi.mock('./client', () => ({ api: { get: vi.fn() } }))
vi.mock('./slices/attachments/attachments.api', () => ({ attachmentsApi: {} }))
vi.mock('./slices/model/model.api', () => ({ modelApi: {} }))

function createPagination() {
  const pagination = usePagination<CollectionInfo, GetLumlCollectionsParams>(
    apiService.getLumlCollections,
  )
  pagination.setParams({
    ...pagination.getParams(),
    organization_id: 'organization-1',
    orbit_id: 'orbit-1',
    search: 'collection',
  })
  return pagination
}

describe('collections pagination', () => {
  beforeEach(() => vi.clearAllMocks())

  it('sends the first page with start_after and preserves collection filters', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], cursor: null } })
    const pagination = createPagination()

    await pagination.getInitialPage()

    expect(api.get).toHaveBeenCalledExactlyOnceWith('/luml/collections', {
      params: {
        organization_id: 'organization-1',
        orbit_id: 'orbit-1',
        limit: 20,
        search: 'collection',
        start_after: null,
      },
    })
  })

  it('loads distinct collections beyond the first 20 and stops at the last page', async () => {
    const collections = Array.from({ length: 25 }, (_, index) => ({
      id: `collection-${index + 1}`,
      name: `collection ${index + 1}`,
    }))
    vi.mocked(api.get).mockImplementation(async (_url, config) => ({
      data:
        config?.params.start_after === 'collection-20'
          ? { items: collections.slice(20), cursor: null }
          : { items: collections.slice(0, 20), cursor: 'collection-20' },
    }))
    const pagination = createPagination()

    await pagination.getInitialPage()
    await pagination.onLazyLoad({ first: 0, last: 20 })

    expect(api.get).toHaveBeenNthCalledWith(2, '/luml/collections', {
      params: {
        organization_id: 'organization-1',
        orbit_id: 'orbit-1',
        limit: 20,
        search: 'collection',
        start_after: 'collection-20',
      },
    })
    expect(pagination.data.value).toEqual(collections)

    await pagination.getNextPage()
    expect(api.get).toHaveBeenCalledTimes(2)
  })

  it('starts from the first page when the selected orbit changes', async () => {
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: { items: [{ id: 'old' }], cursor: 'old' } })
      .mockResolvedValueOnce({ data: { items: [{ id: 'new' }], cursor: null } })
    const pagination = createPagination()
    await pagination.getInitialPage()
    pagination.setParams({ ...pagination.getParams(), orbit_id: 'orbit-2' })

    await pagination.getInitialPage()

    expect(api.get).toHaveBeenLastCalledWith('/luml/collections', {
      params: {
        organization_id: 'organization-1',
        orbit_id: 'orbit-2',
        limit: 20,
        search: 'collection',
        start_after: null,
      },
    })
    expect(pagination.data.value).toEqual([{ id: 'new' }])
  })

  it('does not fetch another page after an empty initial response', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], cursor: null } })
    const pagination = createPagination()

    await pagination.getInitialPage()
    await pagination.getNextPage()

    expect(pagination.data.value).toEqual([])
    expect(api.get).toHaveBeenCalledTimes(1)
  })

  it('preserves loaded collections when the next request fails', async () => {
    const error = new Error('request failed')
    vi.mocked(api.get)
      .mockResolvedValueOnce({ data: { items: [{ id: 'existing' }], cursor: 'existing' } })
      .mockRejectedValueOnce(error)
    const pagination = createPagination()
    await pagination.getInitialPage()

    await expect(pagination.getNextPage()).rejects.toBe(error)

    expect(pagination.data.value).toEqual([{ id: 'existing' }])
  })

  it('keeps cursor pagination for groups and experiments', async () => {
    vi.mocked(api.get).mockResolvedValue({ data: { items: [], cursor: 'next' } })
    const groups = usePagination(apiService.getGroups)
    const experiments = usePagination(apiService.getExperiments)

    await groups.getInitialPage()
    await groups.getNextPage()
    await experiments.getInitialPage()
    await experiments.getNextPage()

    expect(vi.mocked(api.get).mock.calls.map(([, config]) => config?.params)).toEqual([
      { limit: 20, cursor: null },
      { limit: 20, cursor: 'next' },
      { limit: 20, cursor: null },
      { limit: 20, cursor: 'next' },
    ])
  })
})
