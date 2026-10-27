import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { VirtualScrollerLazyEvent } from 'primevue'
import { useExperimentsStore } from '@/store/experiments'
import { useGroupsStore } from '@/store/groups'

const { toast, apiService } = vi.hoisted(() => ({
  toast: { add: vi.fn() },
  apiService: { getExperiments: vi.fn(), getGroups: vi.fn() },
}))

vi.mock('primevue', () => ({ useToast: () => toast }))
vi.mock('@/api/api.service', () => ({ apiService }))

const page = (prefix: string, count: number, cursor: string | null) => ({
  items: Array.from({ length: count }, (_, index) => ({ id: `${prefix}-${index}`, name: prefix })),
  cursor,
})

const lazyEvent = { first: 0, last: 20 } as VirtualScrollerLazyEvent

describe.each([
  {
    name: 'experiments store',
    method: apiService.getExperiments,
    useStore: () => {
      const store = useExperimentsStore()
      return { store, items: () => store.experiments }
    },
  },
  {
    name: 'groups store',
    method: apiService.getGroups,
    useStore: () => {
      const store = useGroupsStore()
      return { store, items: () => store.data }
    },
  },
])('$name next page errors', ({ method, useStore }) => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.clearAllMocks()
  })

  it('reports a failed lazy load with a toast and keeps the list loadable', async () => {
    method
      .mockResolvedValueOnce(page('first', 20, 'next'))
      .mockRejectedValueOnce(new Error('request failed'))
      .mockResolvedValueOnce(page('second', 20, null))
    const { store, items } = useStore()
    await store.getInitialPage()

    await store.onLazyLoad(lazyEvent)

    expect(toast.add).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'request failed' }),
    )
    expect(items()).toHaveLength(20)
    expect(store.isLoading).toBe(false)

    await store.onLazyLoad(lazyEvent)

    expect(items()).toHaveLength(40)
    expect(method).toHaveBeenCalledTimes(3)
  })

  it('reports a failed explicit next page request with a toast', async () => {
    method
      .mockResolvedValueOnce(page('first', 20, 'next'))
      .mockRejectedValueOnce(new Error('request failed'))
    const { store, items } = useStore()
    await store.getInitialPage()

    await expect(store.getNextPage()).resolves.toBeUndefined()

    expect(toast.add).toHaveBeenCalledTimes(1)
    expect(items()).toHaveLength(20)
    expect(store.isLoading).toBe(false)
  })
})
