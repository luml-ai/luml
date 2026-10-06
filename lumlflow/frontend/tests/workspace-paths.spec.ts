import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'

vi.mock('@/api/slices/workspace/workspace.api', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/api/slices/workspace/workspace.api')>()),
  workspaceApi: {
    listFlows: vi.fn(async (directory?: string) => ({ directory: directory ?? 'C:\\start', flows: [] })),
  },
}))

import { workspaceApi } from '@/api/slices/workspace/workspace.api'
import { baseName, parentDirectory } from '@/helpers/path'
import { useWorkspaceStore } from '@/store/workspace'

describe('path helpers', () => {
  it('finds the parent of posix paths', () => {
    expect(parentDirectory('/home/user/flows/')).toBe('/home/user')
    expect(parentDirectory('/home')).toBe('/')
    expect(parentDirectory('/')).toBeNull()
  })

  it('finds the parent of windows paths', () => {
    expect(parentDirectory('C:\\Users\\me\\flows')).toBe('C:\\Users\\me')
    expect(parentDirectory('C:\\Users\\')).toBe('C:\\')
    expect(parentDirectory('C:\\')).toBeNull()
    expect(parentDirectory('C:\\Users\\me/churn.flow')).toBe('C:\\Users\\me')
  })

  it('takes the last segment of either separator', () => {
    expect(baseName('/home/user/churn.flow')).toBe('churn.flow')
    expect(baseName('C:\\Users\\me\\churn.flow\\')).toBe('churn.flow')
    expect(baseName('churn.flow')).toBe('churn.flow')
  })
})

describe('workspace navigation', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.useFakeTimers()
  })

  afterEach(() => {
    vi.useRealTimers()
    vi.mocked(workspaceApi.listFlows).mockClear()
  })

  it('navigates up to the parent of a windows directory', async () => {
    const store = useWorkspaceStore()
    const opened = store.fetchDirectory('C:\\Users\\me\\flows')
    await vi.runAllTimersAsync()
    await opened

    expect(store.canGoUp).toBe(true)
    const up = store.navigateUp()
    await vi.runAllTimersAsync()
    await up

    expect(workspaceApi.listFlows).toHaveBeenLastCalledWith('C:\\Users\\me')
    expect(store.currentDirectory).toBe('C:\\Users\\me')
  })
})
