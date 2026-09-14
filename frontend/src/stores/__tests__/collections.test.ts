import { createPinia, setActivePinia } from 'pinia'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import type { OrbitCollection } from '@/lib/api/orbit-collections/interfaces'

const getCollection = vi.hoisted(() => vi.fn())
const route = vi.hoisted(() => ({
  params: { organizationId: 'org', id: 'orbit' },
}))

vi.mock('@/lib/api', () => ({
  api: { orbitCollections: { getCollection } },
}))
vi.mock('vue-router', () => ({ useRoute: () => route }))

import { useCollectionsStore } from '../collections'

function deferred<T>(): {
  promise: Promise<T>
  resolve: (value: T) => void
} {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

function collection(id: string): OrbitCollection {
  return { id, name: id } as OrbitCollection
}

describe('collections store', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
    getCollection.mockReset()
  })

  it('keeps the latest collection when route reload requests finish out of order', async () => {
    const first = deferred<OrbitCollection>()
    const second = deferred<OrbitCollection>()
    getCollection.mockReturnValueOnce(first.promise).mockReturnValueOnce(second.promise)
    const store = useCollectionsStore()

    const firstLoad = store.setCurrentCollection('models')
    const secondLoad = store.setCurrentCollection('datasets')
    second.resolve(collection('datasets'))
    await secondLoad
    first.resolve(collection('models'))
    await firstLoad

    expect(store.currentCollection?.id).toBe('datasets')
  })

  it('keeps a response that arrives after the registry view reset the store', async () => {
    const load = deferred<OrbitCollection>()
    getCollection.mockReturnValueOnce(load.promise)
    const store = useCollectionsStore()

    const loading = store.setCurrentCollection('models')
    store.reset()
    load.resolve(collection('models'))
    await loading

    expect(store.currentCollection?.id).toBe('models')
  })

  it('drops a response once the collection page itself moved on', async () => {
    const load = deferred<OrbitCollection>()
    getCollection.mockReturnValueOnce(load.promise)
    const store = useCollectionsStore()

    const loading = store.setCurrentCollection('models')
    store.resetCurrentCollection()
    load.resolve(collection('models'))
    await loading

    expect(store.currentCollection).toBeNull()
  })
})
