import { createPinia, setActivePinia } from 'pinia'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { isLocalFlowReachable, useLocalFlowsStore } from '@/stores/local-flows'

const STORAGE_KEY = 'localFlows'

function storedFlows() {
  return JSON.parse(localStorage.getItem(STORAGE_KEY) ?? 'null')
}

describe('local flows store', () => {
  beforeEach(() => {
    localStorage.clear()
    setActivePinia(createPinia())
  })

  afterEach(() => {
    vi.unstubAllGlobals()
  })

  it('keeps every entry under one key, read again by a fresh store', () => {
    const store = useLocalFlowsStore()
    store.addLocalFlow({ name: 'first', address: 'localhost', port: 5000 })
    store.addLocalFlow({ name: 'second', address: 'localhost', port: 5001 })

    expect(storedFlows()).toEqual([
      { name: 'first', address: 'localhost', port: 5000 },
      { name: 'second', address: 'localhost', port: 5001 },
    ])
    setActivePinia(createPinia())
    expect(useLocalFlowsStore().localFlows.map((flow) => flow.port)).toEqual([5000, 5001])
  })

  it('does not depend on the current orbit or user', () => {
    localStorage.setItem('currentOrbitId', JSON.stringify('orbit-a'))
    useLocalFlowsStore().addLocalFlow({ name: 'first', address: 'localhost', port: 5000 })

    localStorage.setItem('currentOrbitId', JSON.stringify('orbit-b'))
    setActivePinia(createPinia())

    expect(useLocalFlowsStore().localFlows).toHaveLength(1)
  })

  it('refuses the same address and port again, naming the existing entry', () => {
    const store = useLocalFlowsStore()
    store.addLocalFlow({ name: 'training', address: 'localhost', port: 5000 })

    expect(() => store.addLocalFlow({ name: 'other', address: 'localhost', port: 5000 })).toThrow(
      'localhost:5000 is already added as "training".',
    )
    expect(store.localFlows).toHaveLength(1)
  })

  it('allows the same name on another port', () => {
    const store = useLocalFlowsStore()
    store.addLocalFlow({ name: 'training', address: 'localhost', port: 5000 })
    store.addLocalFlow({ name: 'training', address: 'localhost', port: 5001 })

    expect(store.localFlows).toHaveLength(2)
  })

  it('removes an entry by address and port', () => {
    const store = useLocalFlowsStore()
    store.addLocalFlow({ name: 'first', address: 'localhost', port: 5000 })
    store.addLocalFlow({ name: 'second', address: 'localhost', port: 5001 })

    store.removeLocalFlow({ address: 'localhost', port: 5000 })

    expect(storedFlows()).toEqual([{ name: 'second', address: 'localhost', port: 5001 }])
  })

  it('ignores stored data that is not a list of entries', () => {
    localStorage.setItem(
      STORAGE_KEY,
      JSON.stringify([{ name: 'ok', address: 'localhost', port: 5000 }, { name: 'broken' }, 7]),
    )
    expect(useLocalFlowsStore().localFlows).toEqual([
      { name: 'ok', address: 'localhost', port: 5000 },
    ])

    localStorage.setItem(STORAGE_KEY, '{not json')
    setActivePinia(createPinia())
    expect(useLocalFlowsStore().localFlows).toEqual([])
  })

  it('checks reachability at the lumlflow status path', async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true })
    vi.stubGlobal('fetch', fetchMock)

    expect(await isLocalFlowReachable({ address: 'localhost', port: 5001 })).toBe(true)
    expect(fetchMock.mock.calls[0]![0]).toBe('http://localhost:5001/api/auth/status')

    fetchMock.mockResolvedValue({ ok: false })
    expect(await isLocalFlowReachable({ address: 'localhost', port: 5001 })).toBe(false)

    fetchMock.mockRejectedValue(new TypeError('Failed to fetch'))
    expect(await isLocalFlowReachable({ address: 'localhost', port: 5001 })).toBe(false)
  })
})
