import { flushPromises, shallowMount } from '@vue/test-utils'
import { createPinia, setActivePinia } from 'pinia'
import { describe, expect, it, vi } from 'vitest'
import { useArtifactLinksStore } from '@/stores/artifact-links/artifact-links'
import { api } from '@/lib/api'
import LinkArtifactCreator from './LinkArtifactCreator.vue'

vi.mock('@/lib/api', () => ({ api: { artifacts: { getOrbitArtifacts: vi.fn() } } }))
vi.mock('vue-router', () => ({
  useRoute: () => ({ params: { organizationId: 'org', id: 'orb', trackId: 'track' } }),
}))
vi.mock('@/stores/orbits', () => ({
  useOrbitsStore: () => ({ currentOrbit: { id: 'orb', organization_id: 'org' } }),
}))
vi.mock('@/stores/tracks', () => ({ useTracksStore: () => ({ currentTrack: null }) }))
vi.mock('primevue', async (original) => ({
  ...(await original<typeof import('primevue')>()),
  useToast: () => ({ add: vi.fn() }),
}))
describe('artifact creator pagination', () => {
  it('loads the next page after reopening with a previously selected collection', async () => {
    const pinia = createPinia()
    setActivePinia(pinia)
    const links = useArtifactLinksStore()
    vi.mocked(api.artifacts.getOrbitArtifacts).mockResolvedValue({
      items: [{ id: 'a1' }] as never,
      cursor: 'next',
    })
    const wrapper = shallowMount(LinkArtifactCreator, {
      global: { plugins: [pinia], renderStubDefaultSlot: true },
    })
    links.showCreator()
    await flushPromises()
    wrapper.getComponent({ name: 'CollectionSelect' }).vm.$emit('update:modelValue', 'col-1')
    await flushPromises()
    links.hideCreator()
    await flushPromises()
    links.showCreator()
    await flushPromises()
    vi.mocked(api.artifacts.getOrbitArtifacts).mockResolvedValueOnce({
      items: [{ id: 'a2' }] as never,
      cursor: null,
    })
    wrapper.getComponent({ name: 'ArtifactsList' }).vm.$emit('lazy-load', { first: 0, last: 1 })
    await flushPromises()
    expect(api.artifacts.getOrbitArtifacts).toHaveBeenLastCalledWith(
      'org',
      'orb',
      expect.objectContaining({ cursor: 'next', collection_ids: [] }),
      expect.any(AbortSignal),
    )
    expect(wrapper.getComponent({ name: 'ArtifactsList' }).props('list')).toEqual([
      { id: 'a1' },
      { id: 'a2' },
    ])
    wrapper.unmount()
  })
})
