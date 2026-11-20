import { beforeEach, describe, expect, it, vi } from 'vitest'
import { createPinia, setActivePinia } from 'pinia'
import { useEvalsStore } from '../index'
import type { ExperimentSnapshotProvider } from '@/interfaces/interfaces'
import {
  FakeBucketSource,
  points,
} from '@/components/dynamic-metrics/__tests__/helpers/fakeBucketSource'

vi.mock('primevue', async (importOriginal) => ({
  ...(await importOriginal<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))

function provider(): ExperimentSnapshotProvider {
  return new FakeBucketSource({
    a: { loss: points(0, 9) },
  }) as unknown as ExperimentSnapshotProvider
}

describe('evals store metric bucket store', () => {
  beforeEach(() => setActivePinia(createPinia()))

  it('disposes the store of a replaced or reset provider', () => {
    const evals = useEvalsStore()
    evals.setProvider(provider())
    const first = evals.metricBucketStore
    evals.setProvider(provider())
    const second = evals.metricBucketStore

    expect(first?.disposed).toBe(true)
    expect(second?.disposed).toBe(false)
    evals.resetProvider()
    expect(second?.disposed).toBe(true)
    expect(evals.metricBucketStore).toBeNull()
  })

  it('keeps the store when the same provider is set again', () => {
    const evals = useEvalsStore()
    const same = provider()
    evals.setProvider(same)
    const first = evals.metricBucketStore
    evals.setProvider(same)

    expect(evals.metricBucketStore).toBe(first)
    expect(first?.disposed).toBe(false)
  })
  it('replaces the store when the same provider is set for other experiments', () => {
    const evals = useEvalsStore()
    const same = provider()
    evals.setProvider(same, ['a', 'c'])
    const first = evals.metricBucketStore
    evals.setProvider(same, ['a', 'c'])
    expect(evals.metricBucketStore).toBe(first)
    evals.setProvider(same, ['a', 'b'])

    expect(first?.disposed).toBe(true)
    expect(evals.metricBucketStore?.modelIds).toEqual(['a', 'b'])
  })
})
