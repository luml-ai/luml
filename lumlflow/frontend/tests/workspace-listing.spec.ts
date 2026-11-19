import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { WorkspaceListing } from '@/api/slices/workspace/workspace.interface'
import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { useWorkspaceStore } from '@/store/workspace'

vi.mock('@/api/slices/workspace/workspace.api', () => ({
  workspaceApi: { listFlows: vi.fn(), openFlows: vi.fn() },
}))

const list = vi.mocked(workspaceApi.listFlows)
const directory = '/project'
function page(numbers: number[], next_offset: number | null, total: number): WorkspaceListing {
  return {
    directory,
    folders: [],
    flows: [],
    files: numbers.map((number) => ({
      name: number + '.txt',
      path: directory + '/' + number + '.txt',
      size: number,
      modified_at: '2026-01-01T00:00:00+00:00',
      is_symlink: false,
    })),
    next_offset,
    total,
  }
}

function pendingPage() {
  let resolve!: (page: WorkspaceListing) => void
  const promise = new Promise<WorkspaceListing>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

beforeEach(() => {
  window.localStorage.clear()
  setActivePinia(createPinia())
  list.mockReset()
})

describe('workspace listing', () => {
  it('appends pages, preserving file metadata and the server order', async () => {
    const first = page([1, 2], 2, 5)
    first.files[0]!.is_symlink = true
    first.files[0]!.size = null
    list
      .mockResolvedValueOnce(first)
      .mockResolvedValueOnce(page([3, 4], 4, 5))
      .mockResolvedValueOnce(page([5], null, 5))

    const store = useWorkspaceStore()
    await store.fetchDirectory(directory)
    expect(store.sortedItems[0]).toMatchObject({ ...first.files[0], type: 'file' })
    expect(store.total).toBe(5)
    expect(store.nextOffset).toBe(2)
    await Promise.all([store.loadMore(), store.loadMore()])
    await store.loadMore()
    await store.loadMore()
    expect(store.sortedItems.map(({ name }) => name)).toEqual([
      '1.txt',
      '2.txt',
      '3.txt',
      '4.txt',
      '5.txt',
    ])
    expect(store.nextOffset).toBeNull()
    expect(list.mock.calls.map((call) => call[2])).toEqual([0, 2, 4])
  })

  it('refreshes the loaded pages together and keeps the previous listing on failure', async () => {
    list.mockResolvedValueOnce(page([1, 2], 2, 5)).mockResolvedValueOnce(page([3, 4], 4, 5))
    const store = useWorkspaceStore()
    await store.fetchDirectory(directory)
    await store.loadMore()

    list
      .mockResolvedValueOnce(page([0, 1], 2, 6))
      .mockRejectedValueOnce(new Error('could not read'))
    await expect(store.refreshDirectory()).rejects.toThrow('could not read')
    expect(store.files.map(({ size }) => size)).toEqual([1, 2, 3, 4])
    expect(store.total).toBe(5)

    list.mockResolvedValueOnce(page([0, 1], 2, 3)).mockResolvedValueOnce(page([2], null, 3))
    const refresh = store.fetchDirectory(directory)
    expect(store.isDirectoryLoading).toBe(false)
    await refresh
    expect(store.files.map(({ size }) => size)).toEqual([0, 1, 2])
    expect(store.total).toBe(3)
    expect(store.nextOffset).toBeNull()
  })

  it('retains the rows and hidden preference when changing the filter fails', async () => {
    list.mockResolvedValueOnce(page([1], null, 1)).mockRejectedValueOnce(new Error('read failed'))
    const store = useWorkspaceStore()
    await store.fetchDirectory(directory)
    await expect(store.setShowHidden(true)).rejects.toThrow('read failed')
    expect(store.showHidden).toBe(false)
    expect(store.sortedItems.map((item) => item.name)).toEqual(['1.txt'])
  })

  it('starts at page one with the new hidden preference and restores it on reload', async () => {
    list
      .mockResolvedValueOnce(page([1], 1, 2))
      .mockResolvedValueOnce(page([2], null, 2))
      .mockResolvedValueOnce(page([0], 1, 3))
      .mockResolvedValueOnce(page([0], 1, 3))
    const store = useWorkspaceStore()
    await store.fetchDirectory(directory)
    await store.loadMore()
    await store.setShowHidden(true)
    expect(list).toHaveBeenLastCalledWith(directory, true, 0)
    expect(store.files.map(({ size }) => size)).toEqual([0])

    setActivePinia(createPinia())
    const reloaded = useWorkspaceStore()
    expect(reloaded.showHidden).toBe(true)
    await reloaded.fetchDirectory(directory)
    expect(list).toHaveBeenLastCalledWith(directory, true, 0)
  })

  it('ignores stale pages from an old directory and from a superseded refresh', async () => {
    const stalePage = pendingPage()
    const staleRefresh = pendingPage()
    list
      .mockResolvedValueOnce(page([1], 1, 2))
      .mockReturnValueOnce(stalePage.promise)
      .mockResolvedValueOnce({ ...page([3], null, 1), directory: '/other' })
      .mockReturnValueOnce(staleRefresh.promise)
      .mockResolvedValueOnce({ ...page([4], null, 1), directory: '/other' })

    const store = useWorkspaceStore()
    await store.fetchDirectory(directory)
    const loadMore = store.loadMore()
    await store.fetchDirectory('/other')
    stalePage.resolve(page([2], null, 2))
    await loadMore
    expect(store.currentDirectory).toBe('/other')

    const refresh = store.refreshDirectory()
    await store.refreshDirectory()
    staleRefresh.resolve({ ...page([3], null, 1), directory: '/other' })
    await refresh
    expect(store.files.map(({ size }) => size)).toEqual([4])
  })

  it('honors a pending show-more request when a watcher refresh arrives', async () => {
    const stalePage = pendingPage()
    list
      .mockResolvedValueOnce(page([1], 1, 2))
      .mockReturnValueOnce(stalePage.promise)
      .mockResolvedValueOnce(page([0], 1, 3))
      .mockResolvedValueOnce(page([1], 2, 3))
    const store = useWorkspaceStore()
    await store.fetchDirectory(directory)
    const loadMore = store.loadMore()
    await store.refreshDirectory()
    stalePage.resolve(page([2], null, 2))
    await loadMore
    expect(store.files.map(({ size }) => size)).toEqual([0, 1])
    expect(store.nextOffset).toBe(2)
  })
})
