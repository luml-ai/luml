import { beforeEach, describe, expect, it, vi } from 'vitest'
import { nextTick } from 'vue'
import { createPinia, setActivePinia } from 'pinia'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import { useEvalsStore } from '../../evals'
import { useTraceStore } from '..'

const addToast = vi.hoisted(() => vi.fn())
vi.mock('primevue', () => ({ useToast: () => ({ add: addToast }) }))

describe('trace store', () => {
  let calls: string[]

  beforeEach(() => {
    calls = []
    setActivePinia(createPinia())
    const provider = {
      resetTracesRequestParams() {
        calls.push('resetTracesRequestParams')
        return Promise.reject(new Error('worker was terminated'))
      },
      getTraces() {
        calls.push('getTraces')
        return Promise.resolve([])
      },
    }
    useEvalsStore().setProvider(provider as unknown as ExperimentSnapshotProvider)
  })

  it('leaves no pending search or error toast after leaving Traces', async () => {
    vi.useFakeTimers()
    try {
      const store = useTraceStore()
      store.setArtifactId('m1')
      store.setRequestParams({ search: 'validation' })
      await nextTick()
      store.reset()
      useEvalsStore().resetProvider()
      await nextTick()
      await vi.runAllTimersAsync()
      expect(addToast).not.toHaveBeenCalled()
      expect(calls).not.toContain('getTraces')
    } finally {
      vi.useRealTimers()
    }
  })

  it('does not leave a failed provider reset unhandled on store reset', async () => {
    useTraceStore().reset()
    await new Promise((resolve) => setTimeout(resolve))

    expect(calls).toEqual(['resetTracesRequestParams'])
  })

  it('does not leave a failed provider reset unhandled when reloading traces', async () => {
    await useTraceStore().getNextPage(true)
    await new Promise((resolve) => setTimeout(resolve))

    expect(calls).toEqual(['resetTracesRequestParams', 'getTraces'])
  })
})
