import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { Flow } from '@/lib/api/flows/interfaces'
import { useFlowsStore } from '@/stores/flows'

const flowsApi = vi.hoisted(() => ({ getList: vi.fn(), remove: vi.fn() }))

vi.mock('@/lib/api', () => ({ api: { flows: flowsApi } }))

function flow(id: string): Flow {
  return { id, name: id } as Flow
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

describe('flows store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    flowsApi.getList.mockReset()
    flowsApi.remove.mockReset()
  })

  it('keeps the latest orbit when an older load answers last', async () => {
    const oldOrbit = deferred<Flow[]>()
    const newOrbit = deferred<Flow[]>()
    flowsApi.getList.mockReturnValueOnce(oldOrbit.promise).mockReturnValueOnce(newOrbit.promise)
    const store = useFlowsStore()

    const oldLoad = store.loadFlows('org', 'old-orbit')
    const newLoad = store.loadFlows('org', 'new-orbit')
    newOrbit.resolve([flow('new')])
    await newLoad
    oldOrbit.resolve([flow('old')])
    await oldLoad

    expect(store.flowsList.map((item) => item.id)).toEqual(['new'])
  })

  it('ignores a load that answers after a reset', async () => {
    const load = deferred<Flow[]>()
    flowsApi.getList.mockReturnValueOnce(load.promise)
    const store = useFlowsStore()

    const loading = store.loadFlows('org', 'orbit')
    store.reset()
    load.resolve([flow('stale')])
    await loading

    expect(store.flowsList).toEqual([])
  })

  it('does not bring back a removed flow from a load started before the removal', async () => {
    flowsApi.getList.mockResolvedValueOnce([flow('a'), flow('b')])
    const store = useFlowsStore()
    await store.loadFlows('org', 'orbit')
    const refresh = deferred<Flow[]>()
    flowsApi.getList.mockReturnValueOnce(refresh.promise)
    flowsApi.remove.mockResolvedValue(undefined)

    const refreshing = store.loadFlows('org', 'orbit')
    await store.removeFlow('org', 'orbit', 'a')
    refresh.resolve([flow('a'), flow('b')])
    await refreshing

    expect(store.flowsList.map((item) => item.id)).toEqual(['b'])
  })
})
