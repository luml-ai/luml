import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { nextTick } from 'vue'
import type { OrbitCollection } from '@/lib/api/orbit-collections/interfaces'
import type { Track, TrackEntry } from '@/lib/api/orbit-tracks/interfaces'
import { useCollectionsList } from '@/hooks/useCollectionsList'
import { useTracksList } from '@/hooks/useTracksList'
import { useTrackEntriesList } from '@/hooks/useTrackEntriesList'
import { useCollectionsStore } from '@/stores/collections'
import { useTracksStore } from '@/stores/tracks'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'

const { getCollectionsList, listTracks, listEntries } = vi.hoisted(() => ({
  getCollectionsList: vi.fn(),
  listTracks: vi.fn(),
  listEntries: vi.fn(),
}))

vi.mock('@/lib/api', () => ({
  api: {
    orbitCollections: { getCollectionsList },
    orbitTracks: { listTracks, listEntries },
  },
}))
vi.mock('vue-router', () => ({ useRoute: () => ({ params: {} }) }))

const requestInfo = { organizationId: 'org', orbitId: 'orbit', trackId: 'track' }

const cases = [
  {
    name: 'useCollectionsList',
    request: getCollectionsList,
    create(syncStore: boolean) {
      const hook = useCollectionsList(2, syncStore)
      const store = useCollectionsStore()
      return {
        ...hook,
        list: hook.collectionsList,
        setItems(ids: string[]) {
          const items = ids.map((id) => ({ id }) as OrbitCollection)
          if (syncStore) store.setCollectionsList(items)
          else hook.collectionsList.value = items
        },
      }
    },
    cursorArgument: 2,
  },
  {
    name: 'useTracksList',
    request: listTracks,
    create(syncStore: boolean) {
      const hook = useTracksList(2, syncStore)
      const store = useTracksStore()
      return {
        ...hook,
        list: hook.tracksList,
        setItems(ids: string[]) {
          const items = ids.map((id) => ({ id }) as Track)
          if (syncStore) store.setTracksList(items)
          else hook.tracksList.value = items
        },
      }
    },
    cursorArgument: 2,
  },
  {
    name: 'useTrackEntriesList',
    request: listEntries,
    create(syncStore: boolean) {
      const hook = useTrackEntriesList(2, syncStore)
      const store = useArtifactLinksStore()
      return {
        ...hook,
        list: hook.entriesList,
        setItems(ids: string[]) {
          const items = ids.map((id) => ({ id }) as TrackEntry)
          if (syncStore) store.setEntriesList(items)
          else hook.entriesList.value = items
        },
      }
    },
    cursorArgument: 3,
  },
]

function page(ids: string[], cursor: string | null) {
  return { items: ids.map((id) => ({ id })), cursor }
}

describe.each(cases)('$name pagination', ({ create, request, cursorArgument }) => {
  describe.each([false, true])('syncStore = %s', (syncStore) => {
    beforeEach(() => {
      setActivePinia(createPinia())
      request.mockReset()
    })

    function mountList() {
      const hook = create(syncStore)
      hook.setRequestInfo(requestInfo)
      return hook
    }

    function requestedCursors() {
      return request.mock.calls.map((call) => call[cursorArgument].cursor)
    }

    it('releases loading after an initial request fails and allows retrying', async () => {
      request.mockRejectedValueOnce(new Error('network')).mockResolvedValueOnce(page(['a'], 'c1'))
      const hook = mountList()

      await expect(hook.getInitialPage()).rejects.toThrow('network')

      expect(hook.isLoading.value).toBe(false)
      expect(hook.pageIndex.value).toBe(0)
      expect(hook.list.value).toEqual([])
      await hook.getInitialPage()
      expect(requestedCursors()).toEqual([null, null])
      expect(hook.list.value.map((item) => item.id)).toEqual(['a'])
      expect(hook.isLoading.value).toBe(false)
    })

    it('releases loading if request information is missing', async () => {
      const hook = create(syncStore)

      await expect(hook.getInitialPage()).rejects.toThrow('Request info not set')

      expect(hook.isLoading.value).toBe(false)
      expect(request).not.toHaveBeenCalled()
    })

    it('allows lazy loading to retry a failed page without losing items or the cursor', async () => {
      request
        .mockResolvedValueOnce(page(['a', 'b'], 'c1'))
        .mockRejectedValueOnce(new Error('network'))
        .mockResolvedValueOnce(page(['b', 'c'], null))
      const hook = mountList()
      await hook.getInitialPage()

      await expect(hook.onLazyLoad({ first: 0, last: 2 })).rejects.toThrow('network')

      expect(hook.isLoading.value).toBe(false)
      expect(hook.pageIndex.value).toBe(1)
      expect(hook.list.value.map((item) => item.id)).toEqual(['a', 'b'])
      await hook.onLazyLoad({ first: 0, last: 2 })
      expect(requestedCursors()).toEqual([null, 'c1', 'c1'])
      expect(hook.list.value.map((item) => item.id)).toEqual(['a', 'b', 'c'])
      expect(hook.isLoading.value).toBe(false)
      expect(hook.pageIndex.value).toBe(2)
    })

    it.each([
      { mutation: 'insertion', ids: ['new', 'a', 'b'], last: 3 },
      { mutation: 'deletion', ids: ['a'], last: 1 },
      { mutation: 'insertion with scroll overshoot', ids: ['new', 'a', 'b'], last: 4 },
      { mutation: 'deleting every item', ids: [], last: 0 },
    ])('loads at the current list end after $mutation', async ({ ids, last }) => {
      request.mockResolvedValueOnce(page(['a', 'b'], 'c1')).mockResolvedValueOnce(page(['c'], null))
      const hook = mountList()
      await hook.getInitialPage()
      hook.setItems(ids)
      await nextTick()

      await hook.onLazyLoad({ first: 0, last })

      expect(requestedCursors()).toEqual([null, 'c1'])
      expect(hook.list.value.map((item) => item.id)).toEqual([...ids, 'c'])
    })

    it('waits until the current list end even at the original page boundary', async () => {
      request.mockResolvedValueOnce(page(['a', 'b'], 'c1'))
      const hook = mountList()
      await hook.getInitialPage()
      hook.setItems(['new', 'a', 'b'])
      await nextTick()

      await hook.onLazyLoad({ first: 0, last: 2 })

      expect(requestedCursors()).toEqual([null])
    })

    it.each([null, ''])('stops when the next cursor is %s', async (cursor) => {
      request.mockResolvedValueOnce(page(['a', 'b'], cursor))
      const hook = mountList()
      await hook.getInitialPage()

      await hook.onLazyLoad({ first: 0, last: 3 })
      await hook.getNextPage()

      expect(requestedCursors()).toEqual([null])
      expect(hook.isLoading.value).toBe(false)
    })

    it('ignores repeated lazy-load events while a request is pending', async () => {
      let resolvePage!: (value: ReturnType<typeof page>) => void
      request
        .mockResolvedValueOnce(page(['a', 'b'], 'c1'))
        .mockReturnValueOnce(new Promise((resolve) => (resolvePage = resolve)))
      const hook = mountList()
      await hook.getInitialPage()

      const loading = hook.onLazyLoad({ first: 0, last: 2 })
      expect(hook.isLoading.value).toBe(true)
      await hook.onLazyLoad({ first: 0, last: 2 })
      expect(requestedCursors()).toEqual([null, 'c1'])

      resolvePage(page(['c'], null))
      await loading
      expect(hook.isLoading.value).toBe(false)
    })
  })
})
