import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ExperimentSnapshotProvider, SpanPayload } from '@/interfaces/interfaces'
import { useEvalsStore } from '..'
import { useTraceStore } from '../../trace'

vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))

function payload(spanId: string): SpanPayload {
  return { attributes: spanId, events: null, links: null, status_message: null }
}

function provider() {
  const getSpanPayload = vi.fn(async (_m: string, _t: string, spanId: string) => payload(spanId))
  return { getSpanPayload } as unknown as ExperimentSnapshotProvider & {
    getSpanPayload: typeof getSpanPayload
  }
}

describe('span payload cache', () => {
  beforeEach(() => {
    setActivePinia(createPinia())
  })

  it('shares one request between concurrent calls for a span', async () => {
    const source = provider()
    const store = useEvalsStore()
    store.setProvider(source)

    const [first, second] = await Promise.all([
      store.loadSpanPayload('m', 't', 's1'),
      store.loadSpanPayload('m', 't', 's1'),
    ])

    expect(first).toEqual(payload('s1'))
    expect(second).toBe(first)
    expect(source.getSpanPayload).toHaveBeenCalledOnce()
    expect(store.getCachedSpanPayload('m', 't', 's1')).toBe(first)
  })

  it('keeps payloads apart per experiment and trace', async () => {
    const store = useEvalsStore()
    store.setProvider(provider())
    await store.loadSpanPayload('m1', 't', 's1')

    expect(store.getCachedSpanPayload('m2', 't', 's1')).toBeUndefined()
    expect(store.getCachedSpanPayload('m1', 't2', 's1')).toBeUndefined()
  })

  it('drops the oldest payload above 100 entries', async () => {
    const store = useEvalsStore()
    store.setProvider(provider())
    for (let index = 0; index <= 100; index++) {
      await store.loadSpanPayload('m', 't', `s${index}`)
    }

    expect(store.getCachedSpanPayload('m', 't', 's0')).toBeUndefined()
    expect(store.getCachedSpanPayload('m', 't', 's1')).toBeDefined()
    expect(store.getCachedSpanPayload('m', 't', 's100')).toBeDefined()
  })

  it('forgets payloads when the provider changes', async () => {
    const store = useEvalsStore()
    store.setProvider(provider())
    await store.loadSpanPayload('m', 't', 's1')

    store.setProvider(provider())

    expect(store.getCachedSpanPayload('m', 't', 's1')).toBeUndefined()
  })

  it.each(['traces', 'evals'])(
    'reads a re-logged span again after refreshing the %s view',
    async (view) => {
      let stored = payload('old')
      const source = {
        getSpanPayload: vi.fn(async () => stored),
        getFreshTraces: vi.fn(async () => []),
      } as unknown as ExperimentSnapshotProvider
      const store = useEvalsStore()
      store.setProvider(source)
      expect((await store.loadSpanPayload('m', 't', 's')).attributes).toBe('old')

      stored = payload('new')
      if (view === 'traces') await useTraceStore().refresh()
      else await store.refresh()

      expect((await store.loadSpanPayload('m', 't', 's')).attributes).toBe('new')
    },
  )
})
