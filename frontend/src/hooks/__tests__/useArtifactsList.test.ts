import { computed } from 'vue'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Artifact } from '@/lib/api/artifacts/interfaces'
import { useArtifactsList } from '@/hooks/useArtifactsList'

const getOrbitArtifacts = vi.hoisted(() => vi.fn())

vi.mock('@/lib/api', () => ({ api: { artifacts: { getOrbitArtifacts } } }))
vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({ artifactsList: [], setArtifactsList: vi.fn() }),
}))

function artifact(id: string): Artifact {
  return { id, name: id } as Artifact
}

function page(ids: string[], cursor: string | null) {
  return { items: ids.map(artifact), cursor }
}

function mountList(excluded: string[]) {
  const list = useArtifactsList(
    2,
    false,
    undefined,
    computed(() => excluded),
  )
  list.setRequestInfo({ organizationId: 'org', orbitId: 'orbit', collectionIds: [] })
  return list
}

function requestedCursors(): (string | null)[] {
  return getOrbitArtifacts.mock.calls.map((call) => (call[2] as { cursor: string | null }).cursor)
}

describe('useArtifactsList', () => {
  beforeEach(() => {
    getOrbitArtifacts.mockReset()
  })

  it('keeps loading pages until an artifact that is not excluded appears', async () => {
    getOrbitArtifacts
      .mockResolvedValueOnce(page(['a', 'b'], 'c1'))
      .mockResolvedValueOnce(page(['c', 'd'], 'c2'))
      .mockResolvedValueOnce(page(['e', 'f'], 'c3'))
      .mockResolvedValueOnce(page(['g', 'h'], null))
    const list = mountList(['a', 'b', 'c', 'd'])

    await list.getInitialPage()

    expect(requestedCursors()).toEqual([null, 'c1', 'c2'])
    expect(list.filteredList.value.map((item) => item.id)).toEqual(['e', 'f'])
    expect(list.isLoading.value).toBe(false)
  })

  it('does not load ahead when the first page already shows something', async () => {
    getOrbitArtifacts.mockResolvedValueOnce(page(['a', 'b'], 'c1'))
    const list = mountList(['a'])

    await list.getInitialPage()

    expect(requestedCursors()).toEqual([null])
    expect(list.filteredList.value.map((item) => item.id)).toEqual(['b'])
  })

  it('skips fully excluded pages on lazy loading and stops at the end of the list', async () => {
    getOrbitArtifacts
      .mockResolvedValueOnce(page(['a', 'b'], 'c1'))
      .mockResolvedValueOnce(page(['c', 'd'], 'c2'))
      .mockResolvedValueOnce(page(['e', 'f'], null))
    const list = mountList(['c', 'd', 'e', 'f'])
    await list.getInitialPage()

    await list.onLazyLoad({ first: 0, last: 2 })

    expect(requestedCursors()).toEqual([null, 'c1', 'c2'])
    expect(list.filteredList.value.map((item) => item.id)).toEqual(['a', 'b'])
    expect(list.isLoading.value).toBe(false)

    await list.onLazyLoad({ first: 0, last: 2 })
    expect(getOrbitArtifacts).toHaveBeenCalledTimes(3)
  })

  it('releases the loading flag when a request fails', async () => {
    getOrbitArtifacts.mockRejectedValueOnce(new Error('network'))
    const list = mountList([])

    await expect(list.getInitialPage()).rejects.toThrow('network')

    expect(list.isLoading.value).toBe(false)
  })

  it('stops pagination when the response has an empty cursor', async () => {
    getOrbitArtifacts.mockResolvedValueOnce(page(['a', 'b'], ''))
    const list = mountList([])
    await list.getInitialPage()

    expect(list.hasNextPage.value).toBe(false)
    await list.getNextPage()
    expect(getOrbitArtifacts).toHaveBeenCalledTimes(1)
  })
})
