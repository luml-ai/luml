import { flushPromises, shallowMount } from '@vue/test-utils'
import { describe, expect, it, vi } from 'vitest'
import DeploymentsFormModelSettings from './DeploymentsFormModelSettings.vue'

const harness = vi.hoisted(() => ({
  getArtifact: vi.fn(),
}))

vi.mock('@/stores/artifacts', () => ({
  useArtifactsStore: () => ({ getArtifact: harness.getArtifact }),
}))
vi.mock('@/stores/collections', () => ({
  useCollectionsStore: () => ({ requestInfo: { organizationId: 'org-1', orbitId: 'orbit-1' } }),
}))
vi.mock('@/stores/orbit-secrets', () => ({
  useSecretsStore: () => ({ loadSecrets: vi.fn().mockResolvedValue(undefined), secretsList: [] }),
}))
vi.mock('@/lib/fnnx/FnnxService', () => ({
  FnnxService: {
    getDynamicAttributes: (manifest: { attribute: string }) => ({
      secrets: [],
      notSecrets: [{ name: manifest.attribute }],
    }),
    getEnvVars: () => ({ secrets: [], notSecrets: [] }),
  },
}))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org-1', id: 'orbit-1' } }),
}))
vi.mock('primevue', async (importOriginal) => {
  const actual = (await importOriginal()) as Record<string, unknown>
  return { ...actual, useToast: () => ({ add: vi.fn() }) }
})

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((res) => {
    resolve = res
  })
  return { promise, resolve }
}

function model(id: string) {
  return { id, manifest: { attribute: `${id}-attribute` } }
}

describe('DeploymentsFormModelSettings', () => {
  it('keeps the latest model when an earlier model request resolves last', async () => {
    const requestA = deferred<ReturnType<typeof model>>()
    const requestB = deferred<ReturnType<typeof model>>()
    harness.getArtifact.mockImplementation((id: string) =>
      id === 'model-a' ? requestA.promise : requestB.promise,
    )
    const wrapper = shallowMount(DeploymentsFormModelSettings, {
      props: { collectionId: 'collection-1', modelId: 'model-a' },
      global: { mocks: { $route: { params: { organizationId: 'org-1', id: 'orbit-1' } } } },
    })
    await flushPromises()

    await wrapper.setProps({ modelId: 'model-b' })
    requestB.resolve(model('model-b'))
    await flushPromises()
    requestA.resolve(model('model-a'))
    await flushPromises()

    expect(harness.getArtifact).toHaveBeenCalledTimes(2)
    const changedModels = wrapper.emitted('modelChanged')?.map(([emitted]) => emitted)
    expect(changedModels?.at(-1)).toEqual(model('model-b'))
    expect(changedModels).not.toContainEqual(model('model-a'))
    expect(wrapper.emitted('update:dynamicAttributes')?.at(-1)).toEqual([
      [{ key: 'model-b-attribute', label: 'model-b-attribute', value: null }],
    ])
  })
})
