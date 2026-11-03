import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import { useEvalsStore } from '../../evals'
import { useTraceStore } from '..'

vi.mock('primevue', () => ({ useToast: () => ({ add: vi.fn() }) }))

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
