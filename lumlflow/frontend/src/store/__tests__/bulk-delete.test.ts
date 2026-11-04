import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'

const apiMocks = vi.hoisted(() => ({
  getGroups: vi.fn(),
  deleteGroup: vi.fn(),
  getExperiments: vi.fn(),
  deleteExperiment: vi.fn(),
}))
const toast = vi.hoisted(() => ({ add: vi.fn() }))

vi.mock('@/api/api.service', () => ({ apiService: apiMocks }))
vi.mock('primevue', () => ({ useToast: () => toast }))

import { useGroupsStore } from '../groups'
import { useExperimentsStore } from '../experiments'

describe.each([
  {
    entity: 'groups',
    deleteOne: apiMocks.deleteGroup,
    refresh: apiMocks.getGroups,
    deleteMany: (ids: string[]) => useGroupsStore().deleteGroups(ids),
  },
  {
    entity: 'experiments',
    deleteOne: apiMocks.deleteExperiment,
    refresh: apiMocks.getExperiments,
    deleteMany: (ids: string[]) => useExperimentsStore().deleteExperiments(ids),
  },
])('$entity bulk delete', ({ entity, deleteOne, refresh, deleteMany }) => {
  beforeEach(() => {
    setActivePinia(createPinia())
    vi.resetAllMocks()
    refresh.mockResolvedValue({ items: [], cursor: null })
  })

  it('reports the number of successful deletes and refreshes the list', async () => {
    deleteOne.mockImplementation(async (id: string) => ({ id }))

    await deleteMany(['first', 'second'])

    expect(deleteOne.mock.calls).toEqual([['first'], ['second']])
    expect(toast.add).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({
        severity: 'success',
        detail: `2 ${entity} deleted successfully`,
      }),
    )
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('surfaces a failed delete while reporting only successful deletes', async () => {
    deleteOne
      .mockResolvedValueOnce({ id: 'first' })
      .mockRejectedValueOnce(new Error('permission denied'))

    await deleteMany(['first', 'second'])

    expect(toast.add).toHaveBeenCalledTimes(2)
    expect(toast.add).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'permission denied' }),
    )
    expect(toast.add).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'success', detail: `1 ${entity} deleted successfully` }),
    )
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('surfaces every rejection without claiming success when all deletes fail', async () => {
    deleteOne
      .mockRejectedValueOnce(new Error('permission denied'))
      .mockRejectedValueOnce(new Error('service unavailable'))

    await deleteMany(['first', 'second'])

    expect(toast.add).toHaveBeenCalledTimes(2)
    expect(toast.add).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'permission denied' }),
    )
    expect(toast.add).toHaveBeenCalledWith(
      expect.objectContaining({ severity: 'error', detail: 'service unavailable' }),
    )
    expect(refresh).toHaveBeenCalledOnce()
  })

  it('uses the existing error fallback for a rejection without an error message', async () => {
    deleteOne.mockRejectedValueOnce(undefined)

    await deleteMany(['first'])

    expect(toast.add).toHaveBeenCalledExactlyOnceWith(
      expect.objectContaining({ severity: 'error', detail: 'Unknown error' }),
    )
  })

  it('does not claim success when no deletes were requested', async () => {
    await deleteMany([])

    expect(deleteOne).not.toHaveBeenCalled()
    expect(toast.add).not.toHaveBeenCalled()
  })
})
