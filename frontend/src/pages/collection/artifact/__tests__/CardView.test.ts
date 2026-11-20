import { createPinia, setActivePinia } from 'pinia'
import { flushPromises, shallowMount } from '@vue/test-utils'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import CardView from '../CardView.vue'
import { useArtifactsStore } from '@/stores/artifacts'
import type { ModelArtifact } from '@/lib/api/artifacts/interfaces'

const SIGNED_URL = 'https://bucket.test/o/card.zip?X-Amz-Signature=secret-4817&X-Amz-Credential=k'

vi.mock('@/lib/bucket-service', async (importOriginal) => ({
  ...(await importOriginal<typeof import('@/lib/bucket-service')>()),
  ModelDownloader: class {
    async getFileFromBucket(): Promise<never> {
      // An axios error keeps the request, URL included, in its config.
      throw Object.assign(new Error(`Request failed with status code 403 for ${SIGNED_URL}`), {
        config: { url: SIGNED_URL },
        response: { status: 403 },
      })
    }
  },
}))

describe('CardView', () => {
  beforeEach(() => setActivePinia(createPinia()))
  afterEach(() => vi.restoreAllMocks())

  it('logs a failed card download without the signed URL', async () => {
    const logged: unknown[][] = []
    vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => logged.push(args))
    const store = useArtifactsStore()
    store.currentArtifact = {
      id: 'model',
      manifest: { producer_tags: [] },
      file_index: { 'card.zip': [0, 10] },
    } as unknown as ModelArtifact

    shallowMount(CardView)
    await flushPromises()

    expect(logged).toHaveLength(1)
    const text = logged.flat().map((value) => (typeof value === 'string' ? value : 'object'))
    expect(text).toEqual([
      'Model card could not be loaded: Request failed with status code 403 for https://bucket.test',
    ])
  })
})
